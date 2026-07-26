const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, 'google_ai_studio_key.txt');
const bootstrapConfig = readConfigFile();
const GAME_DIR = process.env.UU_GAME_DIR || bootstrapConfig.GAME_DIR || 'D:/Unity undergrounds';
const SOURCE_PATH = path.join(GAME_DIR, 'translations', 'global_text_map.json');
const TRANSLATIONS_DIR = path.join(GAME_DIR, 'translations');
const OUTPUT_DIR = path.join(ROOT, 'output');
const GUIDE_PATH = path.join(OUTPUT_DIR, 'gemma_style_guide.json');
const RESULT_PATH = path.join(OUTPUT_DIR, 'global_text_map.gemini.json');
const REPORT_PATH = path.join(OUTPUT_DIR, 'validation_report.json');
const BLOCK_RESULT_PATH = path.join(OUTPUT_DIR, 'block_dialogue_translations.json');

function readConfigFile() {
  const config = {};
  if (!fs.existsSync(CONFIG_PATH)) return config;
  for (const rawLine of fs.readFileSync(CONFIG_PATH, 'utf8').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const equals = line.indexOf('=');
    if (equals < 0) continue;
    config[line.slice(0, equals).trim()] = line.slice(equals + 1).trim();
  }
  return config;
}

function readConfig() {
  const config = readConfigFile();
  if (!config.GOOGLE_AI_STUDIO_API_KEY) {
    throw new Error(`API 키를 먼저 입력하세요: ${CONFIG_PATH}`);
  }
  return config;
}

function normalizeModelName(value) {
  return String(value || '').toLowerCase().replace(/^models\//, '').replace(/[^a-z0-9]+/g, '');
}

async function listModels(apiKey) {
  const models = [];
  let pageToken = '';
  do {
    const url = new URL('https://generativelanguage.googleapis.com/v1beta/models');
    url.searchParams.set('key', apiKey);
    url.searchParams.set('pageSize', '1000');
    if (pageToken) url.searchParams.set('pageToken', pageToken);
    const response = await fetch(url);
    if (!response.ok) throw new Error(`모델 목록 요청 실패: HTTP ${response.status} ${await response.text()}`);
    const body = await response.json();
    models.push(...(body.models || []));
    pageToken = body.nextPageToken || '';
  } while (pageToken);
  return models;
}

function resolveModel(models, hint) {
  const wanted = normalizeModelName(hint);
  const usable = models.filter(model =>
    (model.supportedGenerationMethods || []).includes('generateContent'));
  const scored = usable.map(model => {
    const name = normalizeModelName(model.name);
    const display = normalizeModelName(model.displayName);
    let score = 0;
    if (name === wanted || display === wanted) score = 100;
    else if (name.includes(wanted) || display.includes(wanted)) score = 80;
    else {
      const tokens = String(hint).toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
      score = tokens.filter(token => name.includes(token) || display.includes(token)).length;
    }
    return { model, score };
  }).sort((a, b) => b.score - a.score);
  if (!scored.length || scored[0].score < 80) {
    const candidates = scored.slice(0, 10).map(x => `${x.model.name} (${x.model.displayName || ''})`).join('\n');
    throw new Error(`모델 이름이 정확히 일치하지 않습니다: ${hint}\nAI Studio에서 확인된 유사 후보:\n${candidates}`);
  }
  return scored[0].model.name.replace(/^models\//, '');
}

async function generateJson(apiKey, model, systemInstruction, prompt, temperature = 0.2) {
  const url = new URL(`https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent`);
  url.searchParams.set('key', apiKey);
  const isGemma = /^gemma-/i.test(model);
  const userText = isGemma
    ? `${systemInstruction}\n\nTASK:\n${prompt}\n\nReturn only the requested JSON object or array.`
    : prompt;
  const body = {
    contents: [{ role: 'user', parts: [{ text: userText }] }],
    generationConfig: {
      temperature,
      responseMimeType: 'application/json',
      maxOutputTokens: isGemma ? 4096 : 16384
    }
  };
  if (!isGemma) {
    body.systemInstruction = { parts: [{ text: systemInstruction }] };
  }
  let lastError;
  for (let attempt = 1; attempt <= 5; attempt++) {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (response.ok) {
      const result = await response.json();
      const text = (result.candidates?.[0]?.content?.parts || []).map(part => part.text || '').join('');
      if (!text) throw new Error(`빈 응답: ${model}`);
      try {
        return parseJsonResponse(text, model);
      } catch (formatError) {
        lastError = formatError;
        if (attempt >= 5) throw formatError;
        console.log(`JSON 형식 재생성 ${attempt}/5`);
        await new Promise(resolve => setTimeout(resolve, 5000));
        continue;
      }
    }
    const detail = await response.text();
    lastError = new Error(`${model} 호출 실패: HTTP ${response.status} ${detail}`);
    if (![429, 500, 502, 503, 504].includes(response.status)) throw lastError;
    let waitMs = Math.min(30000, 1500 * 2 ** (attempt - 1));
    if (response.status === 429) {
      const retryInfo = detail.match(/"retryDelay"\s*:\s*"([0-9]+)s"/i);
      const messageDelay = detail.match(/retry in\s+([0-9.]+)s/i);
      const seconds = retryInfo ? Number(retryInfo[1]) : (messageDelay ? Number(messageDelay[1]) : 45);
      waitMs = Math.min(55000, Math.max(5000, Math.ceil(seconds * 1000) + 2000));
      console.log(`할당량 대기 ${Math.ceil(waitMs / 1000)}초 (재시도 ${attempt}/5)`);
    }
    await new Promise(resolve => setTimeout(resolve, waitMs));
  }
  throw lastError;
}

function parseJsonResponse(text, model) {
  const trimmed = text.trim()
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```$/i, '');
  try {
    return JSON.parse(trimmed);
  } catch (_) {
    // Gemma can prepend a short explanation even when JSON output is requested.
    // Extract the widest plausible JSON object/array without logging the API key.
    const objectStart = trimmed.indexOf('{');
    const arrayStart = trimmed.indexOf('[');
    let start;
    if (objectStart < 0) start = arrayStart;
    else if (arrayStart < 0) start = objectStart;
    else start = Math.min(objectStart, arrayStart);
    const objectEnd = trimmed.lastIndexOf('}');
    const arrayEnd = trimmed.lastIndexOf(']');
    const end = Math.max(objectEnd, arrayEnd);
    if (start >= 0 && end > start) {
      try {
        return JSON.parse(trimmed.slice(start, end + 1));
      } catch (_) { /* report a concise format error below */ }
    }
    const preview = trimmed.slice(0, 160).replace(/\s+/g, ' ');
    throw new Error(`${model} 응답에서 JSON을 추출하지 못했습니다: ${preview}`);
  }
}

function loadSource() {
  const root = JSON.parse(fs.readFileSync(SOURCE_PATH, 'utf8'));
  const map = root['99999'];
  if (!map || typeof map !== 'object') throw new Error('global_text_map.json에서 99999 블록을 찾지 못했습니다.');
  return { root, map, entries: Object.entries(map).map(([source, current], id) => ({ id, source, current })) };
}

function splitByCharacters(entries, limit = 42000) {
  const batches = [];
  let batch = [];
  let size = 0;
  for (const entry of entries) {
    const next = JSON.stringify(entry).length + 1;
    if (batch.length && size + next > limit) {
      batches.push(batch);
      batch = [];
      size = 0;
    }
    batch.push(entry);
    size += next;
  }
  if (batch.length) batches.push(batch);
  return batches;
}

function mergeGemmaAnalyses(partials) {
  const termCandidates = [];
  const collectTerms = (node, category = 'general') => {
    if (!node) return;
    if (Array.isArray(node)) {
      for (const item of node) collectTerms(item, category);
      return;
    }
    if (typeof node !== 'object') return;
    if (typeof node.en === 'string' && typeof node.ko === 'string') {
      termCandidates.push({ en: node.en, ko: node.ko, category, evidence: node.evidence || '' });
      return;
    }
    const entries = Object.entries(node);
    if (entries.length && entries.every(([, value]) => typeof value === 'string')) {
      for (const [en, ko] of entries) termCandidates.push({ en, ko, category, evidence: '' });
      return;
    }
    for (const [key, value] of entries) collectTerms(value, key);
  };
  const flattenRules = (node, prefix = '') => {
    const output = [];
    if (typeof node === 'string') return [`${prefix}: ${node}`];
    if (Array.isArray(node)) {
      for (const item of node) output.push(...flattenRules(item, prefix));
    } else if (node && typeof node === 'object') {
      for (const [key, value] of Object.entries(node)) {
        output.push(...flattenRules(value, prefix ? `${prefix}.${key}` : key));
      }
    }
    return output;
  };
  const uniqueStrings = values => [...new Set(values.filter(Boolean))];
  const uniqueObjects = values => {
    const seen = new Set();
    return values.filter(value => {
      const signature = JSON.stringify(value);
      if (seen.has(signature)) return false;
      seen.add(signature);
      return true;
    });
  };

  const characters = [];
  const styleRules = [];
  const uiRules = [];
  const formattingRules = [];
  const ambiguityWarnings = [];
  for (const partial of partials) {
    collectTerms(partial.terms);
    if (Array.isArray(partial.characters)) characters.push(...partial.characters);
    else if (partial.characters) characters.push(partial.characters);
    styleRules.push(...flattenRules(partial.styleRules));
    uiRules.push(...flattenRules(partial.uiRules));
    formattingRules.push(...flattenRules(partial.formattingRules));
    if (Array.isArray(partial.ambiguityWarnings)) ambiguityWarnings.push(...partial.ambiguityWarnings);
    else if (partial.ambiguityWarnings) ambiguityWarnings.push(partial.ambiguityWarnings);
  }

  const groupedTerms = new Map();
  for (const term of termCandidates) {
    const key = term.en.trim().toLocaleLowerCase('en-US');
    if (!key) continue;
    if (!groupedTerms.has(key)) groupedTerms.set(key, { en: term.en, preferred: term.ko, alternatives: [], categories: [], evidence: [] });
    const merged = groupedTerms.get(key);
    if (term.ko !== merged.preferred && !merged.alternatives.includes(term.ko)) merged.alternatives.push(term.ko);
    if (term.category && !merged.categories.includes(term.category)) merged.categories.push(term.category);
    if (term.evidence && !merged.evidence.includes(term.evidence)) merged.evidence.push(term.evidence);
  }
  return {
    generatedBy: 'Gemma 4 31B batch analysis; deterministic local merge',
    terms: [...groupedTerms.values()],
    characters: uniqueObjects(characters),
    styleRules: uniqueStrings(styleRules),
    uiRules: uniqueStrings(uiRules),
    formattingRules: uniqueStrings(formattingRules),
    ambiguityWarnings: uniqueObjects(ambiguityWarnings)
  };
}

async function resolveConfiguredModels(config) {
  const models = await listModels(config.GOOGLE_AI_STUDIO_API_KEY);
  return {
    all: models,
    gemma: resolveModel(models, config.GEMMA_MODEL_HINT || 'gemma 4 31b'),
    gemini: resolveModel(models, config.GEMINI_MODEL_HINT || 'gemini 3.5 flash lite')
  };
}

async function analyze(config, models) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const { entries } = loadSource();
  const useful = entries.filter(x => x.source.trim() && (x.source.length >= 12 || /[A-Z][a-z]+/.test(x.source)));
  const batches = splitByCharacters(useful);
  const partials = [];
  const system = [
    'You are the linguistic director for a Korean localization of Ultima Underworld.',
    'Analyze only; do not translate the entire corpus.',
    'Extract canonical terminology, names, character speech registers, recurring grammar, UI style, and ambiguity warnings.',
    'Use evidence from the supplied English source and existing Korean translation, but correct obvious mistranslations.',
    'Return valid JSON with keys terms, characters, styleRules, uiRules, ambiguityWarnings.'
  ].join('\n');
  for (let i = 0; i < batches.length; i++) {
    const checkpoint = path.join(OUTPUT_DIR, `gemma_analysis_${String(i + 1).padStart(3, '0')}.json`);
    if (fs.existsSync(checkpoint)) {
      partials.push(JSON.parse(fs.readFileSync(checkpoint, 'utf8')));
      console.log(`Gemma 분석 ${i + 1}/${batches.length} 체크포인트 사용`);
      continue;
    }
    console.log(`Gemma 분석 ${i + 1}/${batches.length}`);
    const prompt = `Analyze this corpus segment. Preserve evidence by quoting short source keys.\n${JSON.stringify(batches[i])}`;
    partials.push(await generateJson(config.GOOGLE_AI_STUDIO_API_KEY, models.gemma, system, prompt, 0.15));
    fs.writeFileSync(checkpoint, JSON.stringify(partials.at(-1), null, 2), 'utf8');
  }
  const guide = mergeGemmaAnalyses(partials);
  fs.writeFileSync(GUIDE_PATH, JSON.stringify(guide, null, 2), 'utf8');
  console.log(`분석 가이드 생성 완료: ${GUIDE_PATH}`);
}

function formatSignature(value) {
  return {
    printf: value.match(/%[-+0-9.]*[a-z]/gi) || [],
    braces: value.match(/\{\d+\}/g) || [],
    gameTokens: value.match(/@[A-Z]{2}\d+|\\[0-9mp]/g) || [],
    ampersands: (value.match(/&/g) || []).length,
    newlines: (value.match(/\n/g) || []).length
  };
}

function guideForTranslationBatch(guide, batch) {
  const corpus = batch.map(entry => entry.source).join('\n').toLocaleLowerCase('en-US');
  const relevantTerms = (guide.terms || []).filter(term => {
    const english = String(term.en || '').trim().toLocaleLowerCase('en-US');
    return english && corpus.includes(english);
  });
  return {
    generatedBy: guide.generatedBy,
    terms: relevantTerms,
    characters: guide.characters || [],
    styleRules: guide.styleRules || [],
    uiRules: guide.uiRules || [],
    formattingRules: guide.formattingRules || []
  };
}

function loadUntranslatedBlockEntries() {
  const active = loadSource().map;
  const files = fs.readdirSync(TRANSLATIONS_DIR)
    .filter(name => /^block_3\d+\.json$/i.test(name))
    .sort();
  const bySource = new Map();
  const known = {};
  for (const file of files) {
    const fullPath = path.join(TRANSLATIONS_DIR, file);
    const root = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
    const blockKey = Object.keys(root)[0];
    const block = root[blockKey] || {};
    for (const [entryId, value] of Object.entries(block)) {
      if (typeof value !== 'string' || !value.trim()) continue;
      if (!/[A-Za-z]/.test(value) || /[가-힣]/.test(value)) continue;
      // Pure runtime control expressions must remain untouched.
      if (/^(?:\\[0-9mp]|@[A-Z]{2}\d+|[\s])+$/i.test(value)) continue;
      if (!bySource.has(value)) bySource.set(value, { source: value, occurrences: [] });
      bySource.get(value).occurrences.push({ file, blockKey, entryId });
      if (typeof active[value] === 'string' && /[가-힣]/.test(active[value])) known[value] = active[value];
    }
  }
  const entries = [...bySource.values()].map((entry, id) => ({ id, ...entry }));
  return { entries, known };
}

async function translateBlocks(config, models) {
  if (!fs.existsSync(GUIDE_PATH)) throw new Error(`먼저 analyze를 실행하세요: ${GUIDE_PATH}`);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const guide = JSON.parse(fs.readFileSync(GUIDE_PATH, 'utf8'));
  const { entries, known } = loadUntranslatedBlockEntries();
  const resultMap = fs.existsSync(BLOCK_RESULT_PATH)
    ? JSON.parse(fs.readFileSync(BLOCK_RESULT_PATH, 'utf8'))
    : { ...known };
  for (const [source, translated] of Object.entries(known)) {
    if (!(source in resultMap)) resultMap[source] = translated;
  }
  const pending = entries.filter(entry => !(entry.source in resultMap));
  const batches = splitByCharacters(pending, 8000);
  console.log(`대화 블록 고유 문장 ${entries.length}개, 기존 번역 재사용 ${Object.keys(known).length}개, AI 번역 ${pending.length}개`);
  const system = [
    'Translate Ultima Underworld NPC dialogue and dialogue choices into natural Korean.',
    'Obey the supplied Gemma terminology and character speech-style guide.',
    'Never change id. Return a JSON array of objects with exactly id and translation.',
    'Preserve @SS1, @GI37, \\m, \\p, other backslash control codes, quotes, and newlines exactly.',
    'Broken English spoken by goblins or non-humans should sound intentionally simple, but avoid modern internet slang.',
    'Do not add explanations or markdown.'
  ].join('\n');
  for (let i = 0; i < batches.length; i++) {
    console.log(`누락 대화 번역 ${i + 1}/${batches.length}`);
    const payload = batches[i].map(({ id, source }) => ({ id, source }));
    const batchGuide = guideForTranslationBatch(guide, batches[i]);
    const response = await generateJson(
      config.GOOGLE_AI_STUDIO_API_KEY,
      models.gemini,
      system,
      `STYLE GUIDE:\n${JSON.stringify(batchGuide)}\n\nTEXTS:\n${JSON.stringify(payload)}`,
      0.2
    );
    if (!Array.isArray(response)) throw new Error(`대화 배치 ${i + 1}: JSON 배열이 아닙니다.`);
    const byId = new Map(response.map(item => [Number(item.id), item.translation]));
    for (let supplementAttempt = 1; supplementAttempt <= 3; supplementAttempt++) {
      const missing = batches[i].filter(entry => typeof byId.get(entry.id) !== 'string');
      if (!missing.length) break;
      console.log(`대화 배치 ${i + 1}: 누락 ${missing.length}개 보충 ${supplementAttempt}/3`);
      const supplement = await generateJson(
        config.GOOGLE_AI_STUDIO_API_KEY,
        models.gemini,
        system,
        `STYLE GUIDE:\n${JSON.stringify(batchGuide)}\n\nTranslate ONLY these missing entries:\n${JSON.stringify(missing.map(({ id, source }) => ({ id, source })))}`,
        0.1
      );
      if (Array.isArray(supplement)) for (const item of supplement) byId.set(Number(item.id), item.translation);
    }
    for (const entry of batches[i]) {
      const translated = byId.get(entry.id);
      if (typeof translated !== 'string') throw new Error(`대화 배치 ${i + 1}: id ${entry.id} 누락`);
      resultMap[entry.source] = translated;
    }
    fs.writeFileSync(BLOCK_RESULT_PATH, JSON.stringify(resultMap, null, 2), 'utf8');
  }
  console.log(`누락 대화 번역 완료: ${BLOCK_RESULT_PATH}`);
}

function validateBlockTranslations() {
  if (!fs.existsSync(BLOCK_RESULT_PATH)) throw new Error(`대화 번역 결과가 없습니다: ${BLOCK_RESULT_PATH}`);
  const { entries } = loadUntranslatedBlockEntries();
  const result = JSON.parse(fs.readFileSync(BLOCK_RESULT_PATH, 'utf8'));
  const issues = [];
  for (const entry of entries) {
    const translated = result[entry.source];
    if (typeof translated !== 'string' || !translated.trim()) {
      issues.push({ type: 'missing', source: entry.source });
      continue;
    }
    const expected = formatSignature(entry.source);
    const actual = formatSignature(translated);
    if (JSON.stringify(expected) !== JSON.stringify(actual)) {
      issues.push({ type: 'format_mismatch', source: entry.source, translated, expected, actual });
    }
  }
  console.log(JSON.stringify({ sourceCount: entries.length, resultCount: Object.keys(result).length, issueCount: issues.length, safeToApply: issues.length === 0, issues: issues.slice(0, 30) }, null, 2));
  if (issues.length) process.exitCode = 2;
  return issues;
}

function applyBlockTranslations() {
  const issues = validateBlockTranslations();
  if (issues.length) throw new Error('대화 블록 검증 오류가 있어 적용하지 않았습니다.');
  const result = JSON.parse(fs.readFileSync(BLOCK_RESULT_PATH, 'utf8'));
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupDir = path.join(OUTPUT_DIR, `block_backup_${stamp}`);
  fs.mkdirSync(backupDir, { recursive: true });
  let changedFiles = 0;
  let changedEntries = 0;
  for (const file of fs.readdirSync(TRANSLATIONS_DIR).filter(name => /^block_3\d+\.json$/i.test(name))) {
    const fullPath = path.join(TRANSLATIONS_DIR, file);
    const root = JSON.parse(fs.readFileSync(fullPath, 'utf8'));
    const blockKey = Object.keys(root)[0];
    const block = root[blockKey] || {};
    let changed = false;
    for (const entryId of Object.keys(block)) {
      const source = block[entryId];
      if (typeof source === 'string' && typeof result[source] === 'string' && result[source] !== source) {
        block[entryId] = result[source];
        changed = true;
        changedEntries++;
      }
    }
    if (changed) {
      fs.copyFileSync(fullPath, path.join(backupDir, file));
      fs.writeFileSync(fullPath, JSON.stringify(root, null, 2), 'utf8');
      changedFiles++;
    }
  }
  const globalRoot = JSON.parse(fs.readFileSync(SOURCE_PATH, 'utf8'));
  const globalMap = globalRoot['99999'];
  fs.copyFileSync(SOURCE_PATH, path.join(backupDir, 'global_text_map.json'));
  for (const [source, translated] of Object.entries(result)) globalMap[source] = translated;
  fs.writeFileSync(SOURCE_PATH, JSON.stringify(globalRoot, null, 2), 'utf8');
  console.log(JSON.stringify({ changedFiles, changedEntries, globalEntries: Object.keys(globalMap).length, backupDir }, null, 2));
}

async function translate(config, models) {
  if (!fs.existsSync(GUIDE_PATH)) throw new Error(`먼저 analyze를 실행하세요: ${GUIDE_PATH}`);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const guide = JSON.parse(fs.readFileSync(GUIDE_PATH, 'utf8'));
  const { root, entries } = loadSource();
  const resultMap = fs.existsSync(RESULT_PATH)
    ? JSON.parse(fs.readFileSync(RESULT_PATH, 'utf8'))['99999']
    : {};
  const pending = entries.filter(entry => !(entry.source in resultMap));
  const batches = splitByCharacters(pending, 8000);
  const system = [
    'Translate Ultima Underworld English game text into natural Korean.',
    'Obey the supplied Gemma terminology and speech-style guide.',
    'Never change id. Return a JSON array of objects with exactly id and translation.',
    'Preserve printf tokens, {number} tokens, newlines, and the number/order of & separators exactly.',
    'Underscores in item-name source strings represent article/name formatting; do not reproduce English articles in Korean.',
    'Do not add explanations, markdown, or source text.'
  ].join('\n');
  for (let i = 0; i < batches.length; i++) {
    console.log(`Gemini 번역 ${i + 1}/${batches.length}`);
    const payload = batches[i].map(({ id, source }) => ({ id, source }));
    const batchGuide = guideForTranslationBatch(guide, batches[i]);
    const response = await generateJson(
      config.GOOGLE_AI_STUDIO_API_KEY,
      models.gemini,
      system,
      `STYLE GUIDE:\n${JSON.stringify(batchGuide)}\n\nTEXTS:\n${JSON.stringify(payload)}`,
      0.2
    );
    if (!Array.isArray(response)) throw new Error(`배치 ${i + 1}: JSON 배열이 아닙니다.`);
    const byId = new Map(response.map(item => [Number(item.id), item.translation]));
    for (let supplementAttempt = 1; supplementAttempt <= 3; supplementAttempt++) {
      const missing = batches[i].filter(entry => typeof byId.get(entry.id) !== 'string');
      if (!missing.length) break;
      console.log(`배치 ${i + 1}: 누락 ID ${missing.length}개 보충 ${supplementAttempt}/3`);
      const missingPayload = missing.map(({ id, source }) => ({ id, source }));
      const supplement = await generateJson(
        config.GOOGLE_AI_STUDIO_API_KEY,
        models.gemini,
        system,
        `STYLE GUIDE:\n${JSON.stringify(batchGuide)}\n\nTranslate ONLY these missing entries:\n${JSON.stringify(missingPayload)}`,
        0.1
      );
      if (Array.isArray(supplement)) {
        for (const item of supplement) byId.set(Number(item.id), item.translation);
      }
    }
    for (const entry of batches[i]) {
      const translated = byId.get(entry.id);
      if (typeof translated !== 'string') throw new Error(`배치 ${i + 1}: id ${entry.id} 누락`);
      resultMap[entry.source] = translated;
    }
    const outputRoot = { ...root, '99999': resultMap };
    fs.writeFileSync(RESULT_PATH, JSON.stringify(outputRoot, null, 2), 'utf8');
  }
  console.log(`번역 완료: ${RESULT_PATH}`);
}

function validate() {
  if (!fs.existsSync(RESULT_PATH)) throw new Error(`번역 결과가 없습니다: ${RESULT_PATH}`);
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const source = loadSource();
  const resultRoot = JSON.parse(fs.readFileSync(RESULT_PATH, 'utf8'));
  const result = resultRoot['99999'] || {};
  const issues = [];
  for (const entry of source.entries) {
    if (!(entry.source in result)) {
      issues.push({ type: 'missing_key', source: entry.source });
      continue;
    }
    const translated = result[entry.source];
    if (entry.source.trim() && !String(translated).trim()) issues.push({ type: 'empty_translation', source: entry.source });
    const expected = formatSignature(entry.source);
    const actual = formatSignature(String(translated));
    if (JSON.stringify(expected) !== JSON.stringify(actual)) {
      issues.push({ type: 'format_mismatch', source: entry.source, translated, expected, actual });
    }
  }
  for (const key of Object.keys(result)) {
    if (!(key in source.map)) issues.push({ type: 'extra_key', source: key });
  }
  const report = {
    sourceCount: source.entries.length,
    resultCount: Object.keys(result).length,
    issueCount: issues.length,
    safeToApply: issues.length === 0,
    issues
  };
  fs.writeFileSync(REPORT_PATH, JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify({ ...report, issues: issues.slice(0, 20) }, null, 2));
  if (issues.length) process.exitCode = 2;
}

function repairFromExisting() {
  if (!fs.existsSync(RESULT_PATH)) throw new Error(`번역 결과가 없습니다: ${RESULT_PATH}`);
  const activeRoot = JSON.parse(fs.readFileSync(SOURCE_PATH, 'utf8'));
  const resultRoot = JSON.parse(fs.readFileSync(RESULT_PATH, 'utf8'));
  const active = activeRoot['99999'] || {};
  const result = resultRoot['99999'] || {};
  let restoredUntranslated = 0;
  let restoredObjectNames = 0;
  for (const source of Object.keys(result)) {
    const oldValue = active[source];
    if (typeof oldValue !== 'string' || !/[가-힣]/.test(oldValue)) continue;
    const isObjectName = /^(?:a|an|the|some)_[^.!?]+$/i.test(source) ||
      (source.includes('&') && source.length < 140 && !/[.!?]/.test(source));
    if (isObjectName && result[source] !== oldValue) {
      result[source] = oldValue;
      restoredObjectNames++;
    } else if (!/[가-힣]/.test(String(result[source] || ''))) {
      result[source] = oldValue;
      restoredUntranslated++;
    }
  }
  fs.writeFileSync(RESULT_PATH, JSON.stringify(resultRoot, null, 2), 'utf8');
  console.log(JSON.stringify({ restoredObjectNames, restoredUntranslated }, null, 2));
}

function applyResult() {
  validate();
  if (process.exitCode) throw new Error('검증 오류가 있어 적용하지 않았습니다.');
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backup = `${SOURCE_PATH}.${stamp}.bak`;
  fs.copyFileSync(SOURCE_PATH, backup);
  fs.copyFileSync(RESULT_PATH, SOURCE_PATH);
  console.log(`적용 완료\n백업: ${backup}`);
}

async function main() {
  const command = (process.argv[2] || '').toLowerCase();
  if (!['models', 'analyze', 'translate', 'translate-blocks', 'validate-blocks', 'apply-blocks', 'repair', 'validate', 'apply'].includes(command)) {
    console.log('사용법: node translate_uu.js models|analyze|translate|translate-blocks|validate-blocks|apply-blocks|repair|validate|apply');
    return;
  }
  if (command === 'validate-blocks') return validateBlockTranslations();
  if (command === 'apply-blocks') return applyBlockTranslations();
  if (command === 'repair') return repairFromExisting();
  if (command === 'validate') return validate();
  if (command === 'apply') return applyResult();
  const config = readConfig();
  const models = await resolveConfiguredModels(config);
  console.log(`Gemma 분석 모델: ${models.gemma}`);
  console.log(`Gemini 번역 모델: ${models.gemini}`);
  if (command === 'models') return;
  if (command === 'analyze') return analyze(config, models);
  if (command === 'translate') return translate(config, models);
  if (command === 'translate-blocks') return translateBlocks(config, models);
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
