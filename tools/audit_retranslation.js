const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DEFAULT_TRANSLATION = path.join(ROOT, 'translations', 'global_text_map.json');
const DEFAULT_OUTPUT = path.join(__dirname, 'output', 'retranslation_audit.json');

function parseArgs(argv) {
  const result = { translation: DEFAULT_TRANSLATION, output: DEFAULT_OUTPUT };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--translation') result.translation = path.resolve(argv[++i]);
    else if (argv[i] === '--output') result.output = path.resolve(argv[++i]);
    else if (argv[i] === '--help') result.help = true;
    else throw new Error(`알 수 없는 인수: ${argv[i]}`);
  }
  return result;
}

function loadMap(filePath) {
  const root = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const map = root['99999'];
  if (!map || typeof map !== 'object' || Array.isArray(map)) {
    throw new Error(`${filePath}: 99999 문자열 블록을 찾지 못했습니다.`);
  }
  return map;
}

function formatSignature(value) {
  const text = String(value || '');
  return {
    printf: text.match(/%[-+0-9.]*[a-z]/gi) || [],
    braces: text.match(/\{[^{}\n]+\}/g) || [],
    gameTokens: text.match(/@[A-Z]{2}\d+|\\[0-9mp]/g) || [],
    ampersands: (text.match(/&/g) || []).length,
    newlines: (text.match(/\n/g) || []).length
  };
}

const knownTypos = [
  ['말떫', '오탈자: 말떫'],
  ['주용 손', '오탈자: 주용 손'],
  ['칼리스타n', '한글 이름 뒤 영문 잔존'],
  ['아흐m', '음역 뒤 영문 잔존']
];

const literalGradeTerms = [
  '위대한 명중',
  '매우 위대한 명중',
  '위대한 피해',
  '매우 위대한 피해',
  '위대한 방어',
  '매우 위대한 방어',
  '위대한 강인함',
  '매우 위대한 강인함',
  '비할 데 없는 명중',
  '비할 데 없는 피해',
  '비할 데 없는 방어',
  '비할 데 없는 강인함'
];

function audit(map) {
  const structuralIssues = [];
  const reviewIssues = [];
  const styleStats = {
    totalEntries: 0,
    containsKorean: 0,
    sourceEqualsTranslation: 0,
    containsDangsin: 0,
    containsGeudae: 0,
    archaicEndings: 0
  };

  let id = 0;
  for (const [source, rawTranslation] of Object.entries(map)) {
    id++;
    const translation = String(rawTranslation ?? '');
    styleStats.totalEntries++;
    if (/[가-힣]/.test(translation)) styleStats.containsKorean++;
    if (source === translation) styleStats.sourceEqualsTranslation++;
    if (/당신/.test(translation)) styleStats.containsDangsin++;
    if (/그대/.test(translation)) styleStats.containsGeudae++;
    if (/(?:하노라|했노라|이노라|도다|니라|로다|하오|시오)(?:[.!?]|$)/.test(translation)) {
      styleStats.archaicEndings++;
    }

    if (source.trim() && !translation.trim()) {
      structuralIssues.push({ id, type: 'empty_translation', source });
      continue;
    }

    const expected = formatSignature(source);
    const actual = formatSignature(translation);
    if (JSON.stringify(expected) !== JSON.stringify(actual)) {
      structuralIssues.push({
        id,
        type: 'format_mismatch',
        source,
        translation,
        expected,
        actual
      });
    }

    if (source === translation && /[A-Za-z]/.test(source)) {
      reviewIssues.push({ id, type: 'untranslated', source, translation });
    }

    const glued = translation.match(/[가-힣][a-z]|[a-z][가-힣]/g);
    if (glued) {
      reviewIssues.push({
        id,
        type: 'glued_hangul_latin',
        source,
        translation,
        matches: [...new Set(glued)]
      });
    }

    for (const [needle, reason] of knownTypos) {
      if (translation.includes(needle)) {
        reviewIssues.push({ id, type: 'known_typo', source, translation, reason });
      }
    }

    const literalTerms = literalGradeTerms.filter(term => translation.includes(term));
    if (literalTerms.length) {
      reviewIssues.push({
        id,
        type: 'literal_grade_term',
        source,
        translation,
        matches: literalTerms
      });
    }

    if (/당신/.test(translation) && /(?:그대|자네|네놈|너는|너를)/.test(translation)) {
      reviewIssues.push({
        id,
        type: 'mixed_address_terms',
        source,
        translation
      });
    }
  }

  return {
    generatedAt: new Date().toISOString(),
    structuralIssueCount: structuralIssues.length,
    reviewIssueCount: reviewIssues.length,
    safeForRuntime: structuralIssues.length === 0,
    styleStats,
    structuralIssues,
    reviewIssues
  };
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log('사용법: node tools/audit_retranslation.js [--translation <global_text_map.json>] [--output <report.json>]');
    return;
  }
  const map = loadMap(args.translation);
  const report = audit(map);
  fs.mkdirSync(path.dirname(args.output), { recursive: true });
  fs.writeFileSync(args.output, JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify({
    totalEntries: report.styleStats.totalEntries,
    structuralIssueCount: report.structuralIssueCount,
    reviewIssueCount: report.reviewIssueCount,
    safeForRuntime: report.safeForRuntime,
    output: args.output
  }, null, 2));
  if (report.structuralIssueCount) process.exitCode = 2;
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
