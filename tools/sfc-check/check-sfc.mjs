// 轻量校验：用 @vue/compiler-sfc 解析目标文件，只验证语法，不做打包
import { readFileSync } from 'node:fs';
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc';

const files = process.argv.slice(2);
let bad = 0;
for (const f of files) {
  try {
    const src = readFileSync(f, 'utf-8');
    const { descriptor, errors } = parse(src, { filename: f });
    if (errors && errors.length) {
      console.log('PARSE-FAIL ' + f);
      errors.slice(0, 5).forEach(e => console.log('   ' + (e.message || e)));
      bad++;
      continue;
    }
    if (descriptor.script || descriptor.scriptSetup) {
      compileScript(descriptor, { id: 'x' });
    }
    if (descriptor.template) {
      const r = compileTemplate({
        source: descriptor.template.content,
        filename: f,
        id: 'x',
      });
      if (r.errors && r.errors.length) {
        console.log('TPL-FAIL ' + f);
        r.errors.slice(0, 5).forEach(e => console.log('   ' + (e.message || e)));
        bad++;
        continue;
      }
    }
    console.log('OK  ' + f);
  } catch (e) {
    console.log('THROW ' + f + ' :: ' + e.message);
    bad++;
  }
}
console.log('---');
console.log(bad === 0 ? 'ALL PASS (' + files.length + ' files)' : ('FAILED ' + bad + '/' + files.length));
process.exit(bad === 0 ? 0 : 1);