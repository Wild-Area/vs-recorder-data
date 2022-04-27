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

def is_cjk(lang):
    return lang in ("chs", "cht", "ja", "jakana", "ko")


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


def export_pokes(text_data, data, ctx):
    data["pokemon"] = pokes = {}
    with open(os.path.join(BASE_PATH, "dex", "pokedex.yaml")) as fi:
        poke_dex = yaml.safe_load(fi)
    base_names = text_data["monsname"]
    form_names = text_data["zkn_form"]
    lang = ctx["current_lang"]
    if lang == "en":
        pokemon_names = ctx["pokemon_names"] = {}
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
                pokes[key] = species
                pokemon_names[key] = (species_i, 0)
                continue
            forme_i = find_forme(form_names, forme, species)
            if forme_i is None:
                print((species, forme))
                raise ValueError()
            forme = form_names[forme_i]
            pokes[key] = species if forme == "" else f"{species} ({forme})"
            pokemon_names[key] = (species_i, forme_i)
    else:
        pokemon_names = ctx["pokemon_names"]
        bracket_left, bracket_right = "（）" if is_cjk(lang) else [" (", ')']
        for (key, (i0, i1)) in pokemon_names.items():
            species = base_names[i0]
            forme = form_names[i1]
            pokes[key] = species if forme == "" else f"{species}{bracket_left}{forme}{bracket_right}"
    with open(os.path.join(ctx["output_dir"], lang, "pokemon.yaml"), "w") as fo:
        yaml.safe_dump(pokes, fo, allow_unicode=True)
    return pokes



def export_ids(key, text_data, data, ctx):
    data[key] = ids = {}
    return ids


def process(lang, ctx):
    print(f"Processing {lang}")
    text_data = get_text_resource(lang, ctx["tmpdir"])
    output_dir = os.path.join(ctx["output_dir"], lang)
    os.makedirs(output_dir, exist_ok=True)
    ctx["current_lang"] = lang
    ctx[lang] = data = {}
    data["common"] = common_data = {}
    # export_ids("ability", text_data, data, en_data)
    # export_ids("item", text_data, data, en_data)
    # export_ids("move", text_data, data, en_data)
    # export_ids("nature", text_data, data, en_data)
    export_pokes(text_data, data, ctx)
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
    ctx = {
        "output_dir": output_dir,
        "tmpdir": tmpdir
    }
    process("en", ctx)
    for lang in languages:
        if lang == "en":
            continue
        process(lang, ctx)


if __name__ == "__main__":
    main()