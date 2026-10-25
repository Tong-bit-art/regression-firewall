from regression_firewall.js_exports import (
    canonical_params,
    collect_public_symbols,
    parse_exports,
    strip_comments_and_strings,
)


def names(parsed):
    return set(parsed["symbols"])


def test_named_function_with_params():
    parsed = parse_exports("export function createApp(name, options = {}) { return name }\n")
    assert names(parsed) == {"createApp"}
    entry = parsed["symbols"]["createApp"]
    assert entry["kind"] == "function"
    assert entry["signature"] == "(name, options?)"


def test_async_and_generator_functions():
    parsed = parse_exports(
        "export async function fetchAll(ids) {}\n"
        "export function* iterate(items) {}\n"
    )
    assert names(parsed) == {"fetchAll", "iterate"}
    assert parsed["symbols"]["fetchAll"]["signature"] == "(ids)"


def test_class_interface_type_enum():
    parsed = parse_exports(
        "export class Widget extends Base {}\n"
        "export interface Options { a: string }\n"
        "export type Alias = Map<string, number>\n"
        "export enum Color { Red }\n"
        "export abstract class BaseWidget {}\n"
    )
    assert names(parsed) == {"Widget", "Options", "Alias", "Color", "BaseWidget"}
    kinds = {n: parsed["symbols"][n]["kind"] for n in parsed["symbols"]}
    assert kinds == {"Widget": "class", "Options": "interface", "Alias": "type",
                     "Color": "enum", "BaseWidget": "class"}


def test_default_export():
    parsed = parse_exports("export default function main(a, b) {}\n")
    # in real JS the declaration name is not importable; only "default" is
    assert names(parsed) == {"default"}
    assert parsed["default_export"] is True
    assert parsed["symbols"]["default"]["kind"] == "default"
    assert parsed["symbols"]["default"]["signature"] == "(a, b)"


def test_default_export_anonymous():
    parsed = parse_exports("export default class {}\n")
    assert names(parsed) == {"default"}


def test_const_and_arrow_signatures():
    parsed = parse_exports(
        "export const limit = 10\n"
        "export const add = (a, b) => a + b\n"
        "export const wrap = (prefix: string): string => prefix\n"
        "export const one = x => x\n"
        "export let counter = 0\n"
    )
    assert parsed["symbols"]["limit"]["kind"] == "const"
    assert parsed["symbols"]["limit"]["signature"] is None
    assert parsed["symbols"]["add"]["signature"] == "(a, b)"
    assert parsed["symbols"]["wrap"]["signature"] == "(prefix)"
    assert parsed["symbols"]["one"]["signature"] == "(x)"
    assert parsed["symbols"]["counter"]["kind"] == "let"


def test_comments_and_strings_do_not_create_exports():
    text = (
        "// export function ghost() {}\n"
        "/* export const phantom = 1 */\n"
        'const doc = "export const fake = 2"\n'
        "export const real = 1\n"
    )
    parsed = parse_exports(text)
    assert names(parsed) == {"real"}


def test_template_literal_contents_blanked():
    text = "export const msg = `use export const fake = 1 in docs`\n"
    assert names(parse_exports(text)) == {"msg"}


def test_named_local_export_list():
    parsed = parse_exports(
        "function a() {}\nfunction b() {}\nexport { a, b as bee }\n"
    )
    assert names(parsed) == {"a", "bee"}
    assert parsed["symbols"]["bee"]["kind"] == "local"


def test_cjs_exports():
    parsed = parse_exports(
        "exports.one = function () {}\n"
        "module.exports.two = two\n"
    )
    assert names(parsed) == {"one", "two"}
    assert parsed["symbols"]["one"]["kind"] == "cjs"


def test_line_numbers_are_accurate():
    text = "\n\nexport function third() {}\n"
    parsed = parse_exports(text)
    assert parsed["symbols"]["third"]["line"] == 3


def test_canonical_params_structure_only():
    assert canonical_params("") == "()"
    assert canonical_params("a, b?, c = default>") == "(a, b?, c?)"
    assert canonical_params("...args") == "(...args)"
    # type text and nested structures must not leak into names
    assert canonical_params('callback: (x: number, y: string) => void, opts?: Options') == \
        "(callback, opts?)"


def test_parse_is_deterministic():
    text = "export function a() {}\nexport const b = 2\nexport class C {}\n"
    assert parse_exports(text) == parse_exports(text)


def test_strip_preserves_newlines():
    text = "const a = 'one'\n// comment\nconst b = 2\n"
    stripped = strip_comments_and_strings(text)
    assert stripped.count("\n") == text.count("\n")


# -- re-export resolution (tmp files) ------------------------------------------------


def _write(tmp_path, rel, text):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_named_reexport_resolves_one_hop(tmp_path):
    _write(tmp_path, "src/index.ts", "export { createApp as main } from './app'\n")
    _write(tmp_path, "src/app.ts", "export function createApp(a, b) {}\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert set(resolved["symbols"]) == {"main"}
    entry = resolved["symbols"]["main"]
    assert entry["kind"] == "function"
    assert entry["signature"] == "(a, b)"
    assert entry["origin"].endswith("src/app.ts")
    assert resolved["unresolved"] == []


def test_star_reexport_resolves_names(tmp_path):
    _write(tmp_path, "src/index.ts", "export * from './core'\n")
    _write(tmp_path, "src/core.ts",
           "export function alpha() {}\nexport default class Imp {}\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert set(resolved["symbols"]) == {"alpha"}  # default excluded from export *


def test_namespace_reexport(tmp_path):
    _write(tmp_path, "src/index.ts", "export * as core from './core'\n")
    _write(tmp_path, "src/core.ts", "export const value = 1\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert resolved["symbols"]["core"]["kind"] == "namespace"


def test_nested_barrel_resolution_with_depth(tmp_path):
    _write(tmp_path, "src/index.ts", "export * from './routes'\n")
    _write(tmp_path, "src/routes.ts", "export * from './handlers'\n")
    _write(tmp_path, "src/handlers.ts", "export function handle() {}\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert set(resolved["symbols"]) == {"handle"}


def test_unresolved_specifier_recorded_not_fatal(tmp_path):
    _write(tmp_path, "src/index.ts",
           "export { thing } from './missing'\nexport const local = 1\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert set(resolved["symbols"]) == {"local"}
    assert resolved["unresolved"] == ["./missing"]


def test_package_specifier_unresolved(tmp_path):
    _write(tmp_path, "src/index.ts", "export { useState } from 'react'\n")
    resolved = collect_public_symbols(tmp_path / "src" / "index.ts")
    assert resolved["symbols"] == {}
    assert resolved["unresolved"] == ["react"]


def test_cycle_guard_terminates(tmp_path):
    _write(tmp_path, "src/a.ts", "export * from './b'\nexport const a = 1\n")
    _write(tmp_path, "src/b.ts", "export * from './a'\nexport const b = 2\n")
    resolved = collect_public_symbols(tmp_path / "src" / "a.ts")
    assert set(resolved["symbols"]) == {"a", "b"}
