import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { buildFixture, cleanupFixture } from '../fixtures/buildFixture.js';
import { parseVueSFC, parseVueTemplateSection, parseVueScriptSection,
         parseVueStyleSection, parseDslFileSections, parseNodes } from '../../src/core/parser.js';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

describe('parser', () => {
  let fixture;

  before(() => {
    fixture = buildFixture();
  });

  after(() => {
    cleanupFixture(fixture);
  });

  describe('parseVueSFC', () => {
    it('should extract template, script, and style from Vue SFC', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const content = readFileSync(vuePath, 'utf-8');
      const result = parseVueSFC(content);

      assert.ok(result.template.length > 0, 'template should not be empty');
      assert.ok(result.script.length > 0, 'script should not be empty');
      assert.ok(result.style.length > 0, 'style should not be empty');
    });

    it('should handle content with no template', () => {
      const result = parseVueSFC('<script>export default {}</script>');
      assert.equal(result.template, '');
    });

    it('should handle content with no script', () => {
      const result = parseVueSFC('<template>hello</template>');
      assert.equal(result.script, '');
    });
  });

  describe('parseVueTemplateSection', () => {
    it('should extract template content only', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const content = readFileSync(vuePath, 'utf-8');
      const template = parseVueTemplateSection(content);
      assert.ok(template.includes('div') || template.includes('template'));
    });
  });

  describe('parseVueScriptSection', () => {
    it('should extract script content only', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const content = readFileSync(vuePath, 'utf-8');
      const script = parseVueScriptSection(content);
      assert.ok(script.includes('methods') || script.includes('export'));
    });
  });

  describe('parseVueStyleSection', () => {
    it('should extract style content only', () => {
      const vuePath = join(fixture.root, '.vtj', 'vue', `${fixture.pageIds[0]}.vue`);
      const content = readFileSync(vuePath, 'utf-8');
      const style = parseVueStyleSection(content);
      assert.ok(style.length > 0);
    });
  });

  describe('parseDslFileSections', () => {
    it('should parse DSL JSON into sections', () => {
      const dslPath = join(fixture.root, '.vtj', 'files', `${fixture.pageIds[0]}.json`);
      const content = readFileSync(dslPath, 'utf-8');
      const result = parseDslFileSections(content);
      assert.ok(result.nodes || result.__VERSION__);
    });
  });

  describe('parseNodes', () => {
    it('should parse node tree recursively', () => {
      const nodes = [
        { id: '1', type: 'div', props: { class: 'root' }, children: [
          { id: '2', type: 'span', props: {} }
        ]}
      ];
      const result = parseNodes(nodes, 3);
      assert.ok(result);
    });
  });
});
