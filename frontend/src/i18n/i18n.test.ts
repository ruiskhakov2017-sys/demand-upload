import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { en } from "./en";
import { ru } from "./ru";

const sourceRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

describe("Russian and English localization", () => {
  it("keeps both dictionaries complete and placeholder-compatible", () => {
    const ruKeys = Object.keys(ru).sort();
    const enKeys = Object.keys(en).sort();

    expect(enKeys).toEqual(ruKeys);
    expect(ruKeys.length).toBeGreaterThan(500);

    for (const key of ruKeys) {
      expect(placeholders(en[key]), key).toEqual(placeholders(ru[key]));
    }
  });

  it("contains representative navigation, status, domain, and preference translations", () => {
    expect(ru["ui.39c6387206"]).toBe("Обзор");
    expect(en["ui.39c6387206"]).toBe("Overview");
    expect(ru["status.DOMAIN_BLOCKED"]).toBe("Домен заблокирован");
    expect(en["status.DOMAIN_BLOCKED"]).toBe("Domain blocked");
    expect(ru["domain.blockedMessage"]).toContain("{domain}");
    expect(en["domain.blockedMessage"]).toContain("{reason}");
    expect(ru["preferences.language"]).toBe("Язык интерфейса");
    expect(en["preferences.language"]).toBe("Interface language");
  });

  it("does not leave Russian user-facing text outside the locale dictionaries", () => {
    const sourceFiles = walk(sourceRoot).filter(
      (file) =>
        /\.(ts|tsx)$/.test(file) &&
        !file.includes(`${path.sep}i18n${path.sep}`)
    );

    for (const file of sourceFiles) {
      expect(fs.readFileSync(file, "utf8"), path.relative(sourceRoot, file)).not.toMatch(
        /[А-Яа-яЁё]/
      );
    }
  });

  it("defines every statically referenced translation key in both locales", () => {
    const referenced = new Set<string>();

    for (const file of walk(sourceRoot).filter((item) => /\.(ts|tsx)$/.test(item))) {
      const source = fs.readFileSync(file, "utf8");
      for (const match of source.matchAll(/\bt\(\s*"([^"]+)"/g)) {
        referenced.add(match[1]);
      }
    }

    for (const key of referenced) {
      expect(ru[key], `Missing RU translation for ${key}`).toBeTypeOf("string");
      expect(en[key], `Missing EN translation for ${key}`).toBeTypeOf("string");
    }
  });
});

function placeholders(value: string) {
  return [...value.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
}

function walk(directory: string): string[] {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const target = path.join(directory, entry.name);
    return entry.isDirectory() ? walk(target) : [target];
  });
}
