#!/bin/env python3
import os, sys
import re
from urllib.request import urlretrieve

import yaml

BASE_PATH = os.path.dirname(os.path.dirname(__file__))
LANGUAGES = [
    "chs",
    "cht",
    "de",
    "en",
    "es",
    "fr",
    "it",
    "ja",
    "jakana",
    "ko"
]


class Context:
    pass


def is_cjk(lang):
    return lang in ("chs", "cht", "ja", "jakana", "ko")


def to_kebab_case(name):
    return re.sub(r"\W+|([a-z])([A-Z])", r"\1-\2", name).strip('-').lower()


def get_text_resource(lang, tmpdir):
    output = os.path.join(tmpdir, lang + ".txt")
    if not os.path.exists(output):
        filename = {
            "chs": "ch-simplified",
            "cht": "ch-traditional",
            "ja": "ja-hiragana",
            "jakana": "ja-katakana",
        }.get(lang, lang)
        url = f"https://raw.githubusercontent.com/CPokemon/swsh-text/master/common/{filename}.txt"
        urlretrieve(url, output)
    try:
        with open(output) as fi:
            lines = fi.read().split("\n")
    except:
        with open(output, encoding="utf-16") as fi:
            lines = fi.read().split("\n")
    indices = [i for i, line in enumerate(lines) if line.startswith("Text File")]
    text_data = {}
    for i, index in enumerate(indices):
        key = re.match("^Text File : (?P<key>.+)$", lines[index]).group("key").strip()
        end = indices[i + 1] - 1 if i + 1 < len(indices) else len(lines)
        text_data[key] = lines[index + 2:end]
    return text_data


def find_forme(form_names, forme, species):
    if species in ("Genesect", ):
        return 0
    elif forme.endswith("Gmax"):
        forme = "Gigantamax"
    forme2 = forme.replace("-", " ")
    for i, name in enumerate(form_names):
        if forme in name or forme2 in name:
            return i


def process_pokes(text_data, ctx):
    lang = ctx.current_lang
    print(f"{lang} - pokes")
    base_names = text_data["monsname"]
    form_names = text_data["zkn_form"]
    ctx.data[lang]["pokemon"] = pokes = {}
    keys = ctx.cache.setdefault("pokemon", {})
    if lang == "en":
        with open(os.path.join(BASE_PATH, "dex", "pokedex.yaml")) as fi:
            poke_dex = yaml.safe_load(fi)
        for (key, value) in poke_dex.items():
            # Only import legal Pokemons.
            # All entries missing a tier are illegal.
            if value.get("tier", "Illegal") == "Illegal":
            # if value.get("isNonstandard", None) in ("LGPE", "Future"):
                continue
            species = value.get("baseSpecies", value["name"])
            forme = value.get("forme", None)
            if species == "Nidoran-F":
                species = "Nidoran♀"
            elif species == "Nidoran-M":
                species = "Nidoran♂"
            species = species.replace('\'', '’')
            try:
                species_i = base_names.index(species)
            except ValueError:
                print(species, file=sys.stderr)
                continue
            if forme is None:
                keys[key] = (species_i, 0)
                continue
            forme_i = find_forme(form_names, forme, species)
            if forme_i is None:
                print((species, forme))
                raise ValueError()
            keys[key] = (species_i, forme_i)
    bracket_left, bracket_right = "（）" if is_cjk(lang) else [" (", ')']
    for (key, (i0, i1)) in keys.items():
        species = base_names[i0]
        forme = form_names[i1]
        pokes[key] = species if forme == "" else f"{species}{bracket_left}{forme}{bracket_right}"
    return pokes


def process_ids(key, text_data, ctx):
    lang = ctx.current_lang
    print(f"{lang} - {key}")
    ctx.data[lang][key] = ids = {}
    ctx.data[lang][f"{key}-info"] = descs = {}
    if key == "ability":
        names = text_data["tokusei"][1:]
        info = text_data["tokuseiinfo"][1:]
    elif key == "item":
        names = text_data["itemname"]
        info = text_data["iteminfo"]
    elif key == "move":
        names = text_data["wazaname"][1:] + text_data["gwazaname"]
        info = text_data["wazainfo"][1:] + text_data["gwazainfo"]
    elif key == "nature":
        names = text_data["seikaku"][:-1]
        info = None
    keys = ctx.cache.setdefault(key, {})
    if lang == "en":
        for i, name in enumerate(names):
            key = to_kebab_case(name)
            if key == "":
                continue
            keys[key] = i
    for key, i in keys.items():
        ids[key] = names[i]
        if info is not None:
            descs[key] = info[i]
    return ids, descs


def process_common(ctx):
    lang = ctx.current_lang
    print(f"{lang} - common")
    data = ctx.data[lang]
    common_data = data["common"]
    pass


def export_all(ctx):
    lang = ctx.current_lang
    for key, value in ctx.data[lang].items():
        if len(value) == 0:
            continue
        with open(os.path.join(ctx.output_dir, lang, f"{key}.yaml"), "w") as fo:
            yaml.safe_dump(value, fo, allow_unicode=True)


def process(lang, ctx):
    print(f"Processing {lang}...")
    text_data = get_text_resource(lang, ctx.tmpdir)
    output_dir = os.path.join(ctx.output_dir, lang)
    os.makedirs(output_dir, exist_ok=True)
    ctx.current_lang = lang
    ctx.data[lang] = data = {}
    data["common"] = {}
    process_ids("ability", text_data, ctx)
    process_ids("item", text_data, ctx)
    process_ids("move", text_data, ctx)
    process_ids("nature", text_data, ctx)
    process_common(ctx)
    process_pokes(text_data, ctx)
    export_all(ctx)
    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: ./generate_locales.py path_to/output/ path_to/tmp " + \
            "[languages=chs,cht,de,en,es,fr,it,ja,jakana,ko]", file=sys.stderr)
        exit(1)
    output_dir = os.path.abspath(sys.argv[1])
    tmpdir = os.path.abspath(sys.argv[2])
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(tmpdir, exist_ok=True)
    if len(sys.argv) > 3:
        languages = sys.argv[3].split(",")
    else:
        languages = LANGUAGES.copy()
    assert all(lang in LANGUAGES for lang in languages)
    ctx = Context()
    ctx.output_dir = output_dir
    ctx.tmpdir = tmpdir
    ctx.cache = {}
    ctx.data = {}
    process("en", ctx)
    for lang in languages:
        if lang == "en":
            continue
        process(lang, ctx)


if __name__ == "__main__":
    main()