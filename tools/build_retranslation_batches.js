const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DEFAULT_TRANSLATION = path.join(ROOT, 'translations', 'global_text_map.json');
const DEFAULT_OUTPUT_DIR = path.join(__dirname, 'output', 'retranslation_batches');

function parsePositiveInteger(value, name) {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${name}은 1 이상의 정수여야 합니다.`);
  return parsed;
}

function parseArgs(argv) {
  const result = {
    translation: DEFAULT_TRANSLATION,
    outputDir: DEFAULT_OUTPUT_DIR,
    characterLimit: 12000,
    context: 3,
    fromId: 1,
    toId: Number.MAX_SAFE_INTEGER
  };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === '--translation') result.translation = path.resolve(argv[++i]);
    else if (arg === '--output-dir') result.outputDir = path.resolve(argv[++i]);
    else if (arg === '--character-limit') result.characterLimit = parsePositiveInteger(argv[++i], arg);
    else if (arg === '--context') result.context = parsePositiveInteger(argv[++i], arg);
    else if (arg === '--from-id') result.fromId = parsePositiveInteger(argv[++i], arg);
    else if (arg === '--to-id') result.toId = parsePositiveInteger(argv[++i], arg);
    else if (arg === '--help') result.help = true;
    else throw new Error(`알 수 없는 인수: ${arg}`);
  }
  if (result.fromId > result.toId) throw new Error('--from-id는 --to-id보다 클 수 없습니다.');
  return result;
}

function loadEntries(filePath) {
  const root = JSON.parse(fs.readFileSync(filePath, 'utf8'));
  const map = root['99999'];
  if (!map || typeof map !== 'object' || Array.isArray(map)) {
    throw new Error(`${filePath}: 99999 문자열 블록을 찾지 못했습니다.`);
  }
  return Object.entries(map).map(([source, current], index) => ({
    id: index + 1,
    source,
    current: String(current ?? '')
  }));
}

function categoryFor(source) {
  const value = source.trim();
  if (/^(?:a|an|the|some)_[^.!?]+$/i.test(value) || (value.includes('&') && value.length < 140 && !/[.!?]/.test(value))) {
    return 'item_or_name';
  }
  if (/%[-+0-9.]*[a-z]|\{[^{}\n]+\}|@[A-Z]{2}\d+|\\[0-9mp]/i.test(value)) return 'runtime_or_control';
  if (value.length <= 42 && !/[.!?]/.test(value)) return 'ui_or_term';
  if (/\b(?:thou|thee|thy|thine|dost|hast|art|wilt|canst)\b/i.test(value)) return 'dialogue_or_lore';
  if (/[\n]|["“”']/.test(value) || value.length >= 180) return 'dialogue_or_lore';
  return 'system_or_description';
}

function makeContext(entries, index, radius) {
  const start = Math.max(0, index - radius);
  const end = Math.min(entries.length, index + radius + 1);
  return entries.slice(start, end).map(entry => ({ id: entry.id, source: entry.source }));
}

function splitBatches(entries, characterLimit) {
  const batches = [];
  let batch = [];
  let size = 0;
  for (const entry of entries) {
    const next = JSON.stringify(entry).length + 1;
    if (batch.length && size + next > characterLimit) {
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

function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    console.log([
      '사용법: node tools/build_retranslation_batches.js [옵션]',
      '  --translation <global_text_map.json>',
      '  --output-dir <directory>',
      '  --character-limit <number>',
      '  --context <neighbor count>',
      '  --from-id <number>',
      '  --to-id <number>'
    ].join('\n'));
    return;
  }

  const allEntries = loadEntries(args.translation);
  const selected = allEntries
    .filter(entry => entry.id >= args.fromId && entry.id <= args.toId)
    .map(entry => {
      const index = entry.id - 1;
      return {
        ...entry,
        category: categoryFor(entry.source),
        context: makeContext(allEntries, index, args.context)
      };
    });

  const batches = splitBatches(selected, args.characterLimit);
  fs.rmSync(args.outputDir, { recursive: true, force: true });
  fs.mkdirSync(args.outputDir, { recursive: true });

  const manifest = {
    generatedAt: new Date().toISOString(),
    source: args.translation,
    entryCount: selected.length,
    batchCount: batches.length,
    characterLimit: args.characterLimit,
    contextRadius: args.context,
    range: { fromId: args.fromId, toId: Math.min(args.toId, allEntries.length) },
    batches: []
  };

  batches.forEach((entries, index) => {
    const file = `batch_${String(index + 1).padStart(3, '0')}.json`;
    const payload = {
      instructions: [
        'Ultima Underworld 게임 문자열을 자연스러운 한국어로 재번역한다.',
        'current는 참고만 하고 오역과 직역을 그대로 답습하지 않는다.',
        'id와 source는 변경하지 않는다.',
        'printf, 중괄호 토큰, @SS1 같은 게임 토큰, 역슬래시 제어 코드, 줄바꿈을 보존한다.',
        'UI와 시스템 문장은 간결하게, 대사는 인물의 관계와 인접 문맥을 고려한다.',
        '결과는 [{id, translation}] JSON 배열로 작성한다.'
      ],
      entries
    };
    fs.writeFileSync(path.join(args.outputDir, file), JSON.stringify(payload, null, 2), 'utf8');
    manifest.batches.push({
      file,
      firstId: entries[0].id,
      lastId: entries.at(-1).id,
      entryCount: entries.length
    });
  });

  fs.writeFileSync(path.join(args.outputDir, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');
  console.log(JSON.stringify({
    entryCount: manifest.entryCount,
    batchCount: manifest.batchCount,
    outputDir: args.outputDir
  }, null, 2));
}

try {
  main();
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
