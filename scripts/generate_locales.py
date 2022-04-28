#!/bin/env python3
import os, sys
import re
from urllib.request import urlretrieve

import yaml

BASE_PATH = os.path.dirname(os.path.dirname(__file__))
LANGUAGES = [
    "zhs",
    "zht",
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
    return lang in ("zhs", "zht", "ja", "jakana", "ko")


def to_kebab_case(name):
    return re.sub(r"\W+|([a-z])([A-Z])", r"\1-\2", name).strip('-').lower()


def get_text_resource(lang, tmpdir):
    output = os.path.join(tmpdir, lang + ".txt")
    if not os.path.exists(output):
        filename = {
            "zhs": "ch-simplified",
            "zht": "ch-traditional",
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
    match key:
        case "ability":
            names = text_data["tokusei"][1:]
            info = text_data["tokuseiinfo"][1:]
        case "item":
            names = text_data["itemname"]
            info = text_data["iteminfo"]
        case "move":
            names = text_data["wazaname"][1:] + text_data["gwazaname"]
            info = text_data["wazainfo"][1:] + text_data["gwazainfo"]
        case "nature":
            names = text_data["seikaku"][:-1]
            info = None
        case "type":
            names = text_data["typename"][:-1]
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


VARIABLE_REGEX = re.compile(r"(\[VAR .+?(?:\(.+?\))?\])")

def _parse_variable(v):
    tmp = v.split("[VAR ")
    if len(tmp) == 1:
        return v
    k1 = tmp[1][0:4]
    match k1:
        case "0100":
            return "<player>"
        case "0102":
            return "<@pokemon>"
        case "0103":
            return "<@type>"
        case "0106":
            return "<@ability>"
        case "0107":
            return "<@move>"
        case "0109":
            return "<@item>"
        case "0200":
            return "<@pp>"
        case "010A" | "1002" | "1302" | "1900" | "BD06" | "FF00":
            return ""
        case "0101":
            return ""
            # raise ValueError("Should not reach here (Mega)")
    return ""

def _battle_preprocess(line):
    return "".join([_parse_variable(x) for x in VARIABLE_REGEX.split(line)])


def _battle_text(ctx, range, key, subkeys = None):
    (start, end) = range
    battle = ctx.data["en"]["battle"]
    battle[key] = entry = {}
    indices = {}
    ctx.cache["battle"][key] = {
        "file": ctx.current_file,
        "subkeys": subkeys,
        "indices": indices,
    }
    file = ctx.current_text_data[ctx.current_file]
    for i, line in enumerate(file[start:end]):
        line = _battle_preprocess(line)
        if line is None:
            continue
        k = f"t-{len(entry) + 1}" if subkeys is None else _get_subkey(line)
        entry[k] = line
        indices[k] = i + start
    if subkeys is None and len(entry) == 1:
        battle[key] = list(entry.items())[0]



def _battle_trainer(lines):
    lines = [_battle_preprocess(x) for x in lines]
    prefix, suffix = lines[0].split("<@pokemon>")
    trainer = {
        "player": "<@pokemon>"
    }
    for key, line in zip(["wild", "opponent", "spectator"], lines[1:]):
        assert line.startswith(prefix) and line.endswith(suffix)
        trainer[key] = line.lstrip(prefix).rstrip(suffix)
    return trainer


def process_battle(text_data, ctx):
    lang = ctx.current_lang
    print(f"{lang} - battle")
    ctx.data[lang]["battle"] = battle = {}
    battle[":trainer"] = _battle_trainer(text_data["btl_set"][0:4])
    # if lang != "en":
    #     for key, cached in ctx.cache["battle"].items():
    #         battle[key] = entry = {}
    #         file = text_data[cached["file"]]
    #         subkeys = cached["subkeys"]
    #         for k, index in cached["indices"].items():
    #             _, entry[k] = _battle_preprocess(file[index], subkeys, entry)
    #         if subkeys is None and len(entry) == 1:
    #             battle[key] = list(entry.items())[0]

    #     return battle

    # ctx.cache["battle"] = {}
    # ctx.current_file = "btl_set"
    # _battle_text(ctx, (0, 4), "faint", "op")
    # _battle_text(ctx, (8, 4), "effectiveness", "effect")
    # _battle_text(ctx, (4, len(text_data["btl_set"])), "other")
    return battle


def export_all(ctx):
    lang = ctx.current_lang
    for key, value in ctx.data[lang].items():
        if len(value) == 0:
            continue
        with open(os.path.join(ctx.output_dir, lang, f"{key}.yaml"), "w") as fo:
            yaml.safe_dump(value, fo, allow_unicode=True, sort_keys=False)


def process(lang, ctx):
    print(f"Processing {lang}...")
    text_data = get_text_resource(lang, ctx.tmpdir)
    output_dir = os.path.join(ctx.output_dir, lang)
    os.makedirs(output_dir, exist_ok=True)
    ctx.current_lang = lang
    ctx.current_text_data = text_data
    ctx.data[lang] = data = {}
    # process_ids("ability", text_data, ctx)
    # process_ids("item", text_data, ctx)
    # process_ids("move", text_data, ctx)
    # process_ids("nature", text_data, ctx)
    # process_ids("type", text_data, ctx)
    process_battle(text_data, ctx)
    # process_pokes(text_data, ctx)
    export_all(ctx)
    return data


def main():
    if len(sys.argv) < 3:
        print("Usage: ./generate_locales.py path_to/output/ path_to/tmp " + \
            "[languages=zhs,zht,de,en,es,fr,it,ja,jakana,ko]", file=sys.stderr)
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