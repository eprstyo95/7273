"""
HS 72/73 Classification Telegram Bot
-------------------------------------
Runs on python-telegram-bot v20+ (async).
Deploy via GitHub Actions (see README in repo).
"""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  DECISION TREE
# ─────────────────────────────────────────────

TREE = {
    "start": {
        "q": "🔍 *HS 72/73 Classifier*\n\nIs the product *hollow* — a pipe, tube, or hollow section?",
        "hint": "Any hollow steel product always falls in Chapter 73.",
        "opts": [
            ("Yes — it is hollow", "hollow"),
            ("No — solid or flat", "not_hollow"),
        ],
    },
    "hollow": {
        "q": "Does it have a *weld seam*?",
        "hint": "Seamless = extruded/pierced from billet. Welded = formed from flat strip.",
        "opts": [
            ("No seam — seamless", "seamless"),
            ("Yes — has a weld seam", "welded"),
            ("Fittings / connectors (elbows, flanges)", "r_7307"),
        ],
    },
    "seamless": {
        "q": "What type of *seamless* tube/pipe?",
        "opts": [
            ("Line pipe — oil/gas/water transmission", "r_7304_line"),
            ("Casing/tubing — OCTG (oil well)", "r_7304_octg"),
            ("Precision / mechanical tubes", "r_7304_mech"),
            ("Stainless steel tubes", "r_7304_ss"),
            ("Other alloy steel tubes", "r_7304_alloy"),
        ],
    },
    "welded": {
        "q": "What is the *outside diameter (OD)*?",
        "hint": "406.4 mm threshold separates 7305 (large) from 7306 (standard).",
        "opts": [
            ("OD > 406.4 mm — large diameter pipe", "r_7305"),
            ("OD ≤ 406.4 mm — standard welded pipe", "welded_small"),
        ],
    },
    "welded_small": {
        "q": "Steel type for this welded pipe?",
        "opts": [
            ("Non-alloy / carbon steel", "r_7306_c"),
            ("Stainless steel (Cr ≥ 10.5%)", "r_7306_ss"),
            ("Other alloy steel", "r_7306_alloy"),
        ],
    },
    "not_hollow": {
        "q": "Has the steel been *fabricated* into a recognisable end-use article?\n\n_(Cut, drilled, welded, assembled for a specific function)_",
        "opts": [
            ("Yes — finished/fabricated article", "fabricated"),
            ("No — basic material form (plate, bar, coil, section)", "ch72_entry"),
        ],
    },
    "fabricated": {
        "q": "What *category* of finished article is it?",
        "opts": [
            ("Structures — bridges, towers, frames, masts", "r_7308"),
            ("Tanks / reservoirs / containers", "tanks"),
            ("Fasteners — bolts, nuts, screws, washers, rivets", "r_7318"),
            ("Springs (leaf, coil, torsion)", "r_7320"),
            ("Stranded wire / wire rope / cables / slings", "r_7312"),
            ("Household / kitchen articles", "r_7323"),
            ("Railway track material", "r_7302"),
            ("Sheet piling", "r_7301"),
            ("Sanitary ware (sinks, baths)", "r_7324"),
            ("Stoves, cookers, heaters", "r_7321"),
            ("Radiators / heating boilers", "r_7322"),
            ("Nails, staples, drawing pins", "r_7317"),
            ("Barbed wire / fencing wire", "r_7313"),
            ("Chain-link / wire mesh / grating", "r_7314"),
            ("Other article (residual)", "r_7326"),
        ],
    },
    "tanks": {
        "q": "What is the *capacity* of the container?",
        "opts": [
            ("Capacity > 300 L — large tank/reservoir", "r_7309"),
            ("Capacity ≤ 300 L — small drum/can/box", "r_7310"),
            ("Compressed gas container (LPG cylinder, gas bottle)", "r_7311"),
        ],
    },
    "ch72_entry": {
        "q": "What is the *form* of the steel?",
        "opts": [
            ("Flat — plate, sheet, strip, coil", "flat"),
            ("Long — bar, rod, wire, section", "long"),
            ("Semi-finished — billet, slab, bloom, ingot", "semi"),
            ("Raw / pig iron, ferro-alloys, scrap", "raw"),
        ],
    },
    "raw": {
        "q": "What type of raw/primary product?",
        "opts": [
            ("Pig iron (from blast furnace)", "r_7201"),
            ("Ferro-alloys (ferro-Mn, ferro-Si etc.)", "r_7202"),
            ("Ferrous scrap / waste / re-melt ingots", "r_7204"),
        ],
    },
    "semi": {
        "q": "Steel type for this *semi-finished* product?",
        "hint": "Semi-finished = billets, slabs, blooms — not ready for end use.",
        "opts": [
            ("Non-alloy (plain carbon) steel", "r_7207"),
            ("Stainless steel (Cr ≥ 10.5%)", "r_7218"),
            ("Other alloy steel", "r_7224"),
        ],
    },
    "flat": {
        "q": "What is the *width* of the flat product?",
        "hint": "The 600 mm boundary is the primary split for all flat products.",
        "opts": [
            ("Width ≥ 600 mm — wide flat product", "flat_wide"),
            ("Width < 600 mm — narrow strip", "flat_narrow"),
        ],
    },
    "flat_wide": {
        "q": "What is the *steel type*?",
        "opts": [
            ("Non-alloy / carbon steel", "flat_wide_c"),
            ("Stainless steel (Cr ≥ 10.5%)", "flat_wide_ss"),
            ("Other alloy steel (not stainless)", "flat_wide_alloy"),
        ],
    },
    "flat_wide_c": {
        "q": "Is there a *surface coating*, or is it bare?\n\n_(Coating overrides rolling method for subheading)_",
        "opts": [
            ("Zinc-coated — hot-dip galvanised", "r_7210_zn_hd"),
            ("Zinc-coated — electrogalvanised", "r_7210_zn_eg"),
            ("Tin-plated (tinplate)", "r_7210_sn"),
            ("Aluminium / aluminium-zinc coated", "r_7210_al"),
            ("Painted / lacquered / plastic-coated", "r_7210_paint"),
            ("Other metallic coating", "r_7210_other"),
            ("Bare — hot-rolled (HR)", "r_7208"),
            ("Bare — cold-rolled (CR)", "r_7209"),
        ],
    },
    "flat_wide_ss": {
        "q": "Is it *hot-rolled* or *cold-rolled*?",
        "opts": [
            ("Hot-rolled", "r_7219_hr"),
            ("Cold-rolled", "r_7219_cr"),
            ("Coated or clad stainless", "r_7219_clad"),
        ],
    },
    "flat_wide_alloy": {
        "q": "Alloy steel wide flat — coating or rolling method?",
        "hint": "Key: zinc-coated OTHER ALLOY steel → 7225.92 (not 7210!)",
        "opts": [
            ("Hot-rolled — bare", "r_7225_hr"),
            ("Cold-rolled — bare", "r_7226_cr"),
            ("Zinc-coated (HDG or EG)", "r_7225_zn"),
            ("Other metallic coating", "r_7225_other"),
            ("Painted / lacquered / plastic-coated", "r_7226_paint"),
        ],
    },
    "flat_narrow": {
        "q": "Steel type for narrow strip (< 600 mm)?",
        "opts": [
            ("Non-alloy / carbon steel", "flat_narrow_c"),
            ("Stainless steel (Cr ≥ 10.5%)", "r_7220_ss"),
            ("Other alloy steel", "r_7226_narrow"),
        ],
    },
    "flat_narrow_c": {
        "q": "Is it *coated* or bare?",
        "opts": [
            ("Bare — hot-rolled", "r_7211_hr"),
            ("Bare — cold-rolled", "r_7211_cr"),
            ("Coated (any coating)", "r_7212"),
        ],
    },
    "long": {
        "q": "What is the *form* of the long product?",
        "opts": [
            ("Wire rod — coiled, hot-rolled", "long_wirerod"),
            ("Bars & rods — straight solid lengths", "long_bars"),
            ("Sections — I, H, U, L, T, Z profiles", "long_sections"),
            ("Wire — cold-drawn, fine gauge, in coils", "long_wire"),
        ],
    },
    "long_wirerod": {
        "q": "Steel type for *wire rod*?",
        "opts": [
            ("Non-alloy steel", "r_7213"),
            ("Stainless steel", "r_7221"),
            ("Other alloy steel", "r_7227"),
        ],
    },
    "long_bars": {
        "q": "Steel type and production method for *bars/rods*?",
        "opts": [
            ("Non-alloy — hot-rolled / forged / extruded", "r_7214"),
            ("Non-alloy — cold-formed / bright bar", "r_7215"),
            ("Stainless steel bars & rods", "r_7222_bar"),
            ("Other alloy steel bars & rods", "r_7228_bar"),
        ],
    },
    "long_sections": {
        "q": "Steel type for *sections/profiles*?",
        "hint": "Sections = I-beam, H-beam, U-channel, angle (L), T-section, Z-section.",
        "opts": [
            ("Non-alloy steel sections", "r_7216"),
            ("Stainless steel sections", "r_7222_sec"),
            ("Other alloy steel sections", "r_7228_sec"),
        ],
    },
    "long_wire": {
        "q": "Steel type for *wire* (cold-drawn)?",
        "hint": "Wire = cold-drawn from wire rod; finer gauge; neat coils. Different from wire rod (7213).",
        "opts": [
            ("Non-alloy steel wire", "r_7217"),
            ("Stainless steel wire", "r_7223"),
            ("Other alloy steel wire", "r_7229"),
        ],
    },
}

# ─────────────────────────────────────────────
#  RESULTS
# ─────────────────────────────────────────────

RESULTS = {
    "r_7201": {
        "hs": "7201",
        "name": "Pig iron and spiegeleisen",
        "desc": "Cast iron from blast furnace (>2% C). In pigs, blocks or other primary forms.",
        "examples": "Haematite pig iron, foundry pig iron, basic pig iron",
        "warn": None,
    },
    "r_7202": {
        "hs": "7202",
        "name": "Ferro-alloys",
        "desc": "Iron alloys with high alloying element content, used as additives in steelmaking.",
        "examples": "Ferro-manganese, ferro-silicon, ferro-chromium, ferro-nickel",
        "warn": None,
    },
    "r_7204": {
        "hs": "7204",
        "name": "Ferrous waste and scrap; re-melting scrap ingots",
        "desc": "Scrap iron/steel for re-melting. Also ingots specifically for re-melting.",
        "examples": "Steel turnings, stampings, offcuts, re-melting ingots",
        "warn": None,
    },
    "r_7207": {
        "hs": "7207",
        "name": "Semi-finished products of non-alloy steel",
        "desc": "Billets, blooms, slabs of non-alloy steel. Not further worked than hot-rolled or continuously cast.",
        "examples": "Billet (square), slab (rectangular), bloom (larger square section)",
        "warn": None,
    },
    "r_7208": {
        "hs": "7208",
        "name": "Flat-rolled, non-alloy, ≥600 mm, hot-rolled, uncoated",
        "desc": "Wide hot-rolled flat steel — plates, sheets, coils. Mill scale surface. Not coated.",
        "examples": "HR coil, HR plate, HR sheet, HRPO (hot-rolled pickled & oiled)",
        "warn": "⚠️ If zinc or any coating applied → reclassify to 7210",
    },
    "r_7209": {
        "hs": "7209",
        "name": "Flat-rolled, non-alloy, ≥600 mm, cold-rolled, uncoated",
        "desc": "Wide cold-rolled flat steel. Smoother surface, tighter tolerances than HR. Uncoated.",
        "examples": "CR coil (CRC), cold-reduced sheet, full-hard CR, skin-passed CR",
        "warn": "⚠️ If coating applied → reclassify to 7210",
    },
    "r_7210_zn_hd": {
        "hs": "7210.41",
        "name": "Flat-rolled, non-alloy, ≥600 mm, hot-dip galvanised (zinc)",
        "desc": "Wide non-alloy flat steel with zinc applied by hot-dip galvanising process.",
        "examples": "HDG coil, hot-dip galvanised plate, galvanised corrugated sheet",
        "warn": "⚠️ Width must be ≥600 mm. If <600 mm → 7212",
    },
    "r_7210_zn_eg": {
        "hs": "7210.49",
        "name": "Flat-rolled, non-alloy, ≥600 mm, electrogalvanised (zinc)",
        "desc": "Wide non-alloy flat steel with zinc applied by electrolytic process.",
        "examples": "Electrogalvanised (EG) sheet/coil, electroplated galvanised strip",
        "warn": "⚠️ Width must be ≥600 mm. If <600 mm → 7212",
    },
    "r_7210_sn": {
        "hs": "7210.11 / 7210.12",
        "name": "Flat-rolled, non-alloy, ≥600 mm, tin-plated (tinplate)",
        "desc": "Wide flat non-alloy steel with tin coating. 7210.11 = thickness ≤0.5 mm; 7210.12 = >0.5 mm.",
        "examples": "Tinplate for food cans, tin-free steel (TFS), blackplate + tin",
        "warn": None,
    },
    "r_7210_al": {
        "hs": "7210.61 / 7210.69",
        "name": "Flat-rolled, non-alloy, ≥600 mm, aluminium-coated",
        "desc": "Coated with aluminium (7210.61) or aluminium-zinc alloy (7210.69) e.g. Galvalume/Zincalume.",
        "examples": "Aluminised steel, Galvalume coil, Zincalume, AZ-coated steel (55% Al-Zn)",
        "warn": None,
    },
    "r_7210_paint": {
        "hs": "7210.70",
        "name": "Flat-rolled, non-alloy, ≥600 mm, painted/lacquered/plastic-coated",
        "desc": "Paint, lacquer, or plastic film on wide flat non-alloy steel.",
        "examples": "Pre-painted (PPGI) coil, colour-coated steel, plastic-laminated sheet",
        "warn": None,
    },
    "r_7210_other": {
        "hs": "7210.90",
        "name": "Flat-rolled, non-alloy, ≥600 mm, other coating (clad, lead etc.)",
        "desc": "Other metallic coatings not elsewhere specified — lead, chromium-plated, clad.",
        "examples": "Terne plate (lead-tin), chrome-coated steel, bimetallic clad sheet",
        "warn": None,
    },
    "r_7211_hr": {
        "hs": "7211.13–7211.19",
        "name": "Flat-rolled, non-alloy, <600 mm, hot-rolled, uncoated",
        "desc": "Narrow hot-rolled strip of non-alloy steel. Subheadings split by thickness.",
        "examples": "Narrow HR strip, slit HR coil <600 mm wide",
        "warn": None,
    },
    "r_7211_cr": {
        "hs": "7211.23 / 7211.29",
        "name": "Flat-rolled, non-alloy, <600 mm, cold-rolled, uncoated",
        "desc": "Narrow cold-rolled strip of non-alloy steel.",
        "examples": "Narrow CR strip, slit CR coil <600 mm wide",
        "warn": None,
    },
    "r_7212": {
        "hs": "7212",
        "name": "Flat-rolled, non-alloy, <600 mm, clad/plated/coated",
        "desc": "Narrow flat non-alloy steel with any coating — zinc, tin, paint, plastic etc.",
        "examples": "Narrow galvanised strip, pre-painted narrow strip, tin-coated narrow strip",
        "warn": None,
    },
    "r_7213": {
        "hs": "7213",
        "name": "Wire rod of non-alloy steel (coils, hot-rolled)",
        "desc": "Hot-rolled solid section in irregularly wound coils. Used as feedstock for wire drawing.",
        "examples": "5.5 mm, 6 mm, 8 mm, 10 mm wire rod in coil form; CHQ wire rod",
        "warn": "⚠️ Not to be confused with 7217 wire (cold-drawn, finer gauge)",
    },
    "r_7214": {
        "hs": "7214",
        "name": "Bars and rods of non-alloy steel, hot-rolled / forged / extruded",
        "desc": "Solid long products in straight lengths — round, square, flat, hexagonal. HR or forged.",
        "examples": "Rebar (deformed bar), round bar, square bar, flat bar, hexagonal bar",
        "warn": None,
    },
    "r_7215": {
        "hs": "7215",
        "name": "Bars and rods of non-alloy steel, cold-formed / cold-finished",
        "desc": "Bars further worked than 7214 — cold-drawn, cold-rolled, cold-turned.",
        "examples": "Bright bar (cold-drawn), silver steel, ground bar, peeled bar",
        "warn": None,
    },
    "r_7216": {
        "hs": "7216",
        "name": "Angles, shapes and sections of non-alloy steel",
        "desc": "Products with I, H, U, L, T, Z or other structural cross-section profile.",
        "examples": "Universal beam (I/H), channel (U/C), angle (L), T-bar, Z-section, bulb flat",
        "warn": "⚠️ Once cut, drilled and assembled into a structure → reclassify to 7308",
    },
    "r_7217": {
        "hs": "7217",
        "name": "Wire of non-alloy steel",
        "desc": "Cold-drawn from wire rod; neat closely wound coils; small diameter. Can be coated.",
        "examples": "Galvanised wire, barbed wire strand, copper-coated welding wire, drawn wire",
        "warn": "⚠️ Stranded/twisted multiple wires → reclassify to 7312",
    },
    "r_7218": {
        "hs": "7218",
        "name": "Stainless steel — ingots or semi-finished products",
        "desc": "Ingots, billets, slabs, blooms of stainless steel (Cr ≥ 10.5%).",
        "examples": "Stainless billet, stainless slab for rolling",
        "warn": None,
    },
    "r_7219_hr": {
        "hs": "7219.11–7219.14",
        "name": "Flat-rolled stainless, ≥600 mm, hot-rolled",
        "desc": "Wide hot-rolled stainless flat product. Subheadings by thickness: >10 mm / 4.75–10 mm / 3–4.75 mm / <3 mm.",
        "examples": "Stainless HR coil/plate — grades 304, 316, 430",
        "warn": None,
    },
    "r_7219_cr": {
        "hs": "7219.31–7219.35",
        "name": "Flat-rolled stainless, ≥600 mm, cold-rolled",
        "desc": "Wide cold-rolled stainless flat product. Subheadings by thickness.",
        "examples": "2B finish stainless CR coil, BA finish, No.4 finish — grades 304, 316",
        "warn": None,
    },
    "r_7219_clad": {
        "hs": "7219.90",
        "name": "Flat-rolled stainless, ≥600 mm, other (clad/coated)",
        "desc": "Stainless wide flat with additional coating or cladding not elsewhere specified.",
        "examples": "Clad stainless plate, coated stainless sheet",
        "warn": None,
    },
    "r_7220_ss": {
        "hs": "7220",
        "name": "Flat-rolled stainless steel, <600 mm",
        "desc": "Narrow stainless flat — HR, CR, or coated/clad. Width <600 mm.",
        "examples": "Narrow stainless strip, slit stainless coil, stainless shim stock",
        "warn": None,
    },
    "r_7221": {
        "hs": "7221",
        "name": "Wire rod of stainless steel",
        "desc": "Hot-rolled stainless steel in irregularly wound coils. Feedstock for stainless wire drawing.",
        "examples": "Stainless wire rod coil — grades 304, 316, 310",
        "warn": None,
    },
    "r_7222_bar": {
        "hs": "7222.10–7222.30",
        "name": "Bars and rods of stainless steel",
        "desc": "Solid straight stainless products — bars, rods. HR, CR, or cold-finished.",
        "examples": "Stainless round bar, flat bar, hex bar — grades 304, 316, 17-4PH",
        "warn": None,
    },
    "r_7222_sec": {
        "hs": "7222.40",
        "name": "Sections of stainless steel",
        "desc": "Stainless steel I, H, U, L, T, Z profiles.",
        "examples": "Stainless angle, stainless channel, stainless T-bar",
        "warn": None,
    },
    "r_7223": {
        "hs": "7223",
        "name": "Wire of stainless steel",
        "desc": "Cold-drawn stainless wire. Can be coated or uncoated.",
        "examples": "Stainless welding wire, stainless spring wire, stainless woven wire feedstock",
        "warn": None,
    },
    "r_7224": {
        "hs": "7224",
        "name": "Other alloy steel — ingots or semi-finished products",
        "desc": "Ingots, billets, blooms, slabs of other alloy steel (not stainless).",
        "examples": "Alloy steel billet (Cr-Mo, Mn, Ni-Cr), tool steel ingot",
        "warn": None,
    },
    "r_7225_hr": {
        "hs": "7225.30 / 7225.40",
        "name": "Flat-rolled other alloy steel, ≥600 mm, hot-rolled, uncoated",
        "desc": "Wide HR flat product of other alloy steel (not stainless). 7225.30 = not in coils; 7225.40 = in coils.",
        "examples": "HSLA coil, boron steel HR plate, Mn-steel wide plate, DP steel HR",
        "warn": "⚠️ If zinc-coated → reclassify to 7225.92 (NOT 7210)",
    },
    "r_7226_cr": {
        "hs": "7226.91 / 7226.92",
        "name": "Flat-rolled other alloy steel, ≥600 mm, cold-rolled, uncoated",
        "desc": "Wide CR flat product of other alloy steel.",
        "examples": "Silicon/electrical steel (CRGO, CRNO), HSLA CR coil, dual-phase CR",
        "warn": "⚠️ Silicon electrical steel (transformer/motor core) classifies here",
    },
    "r_7225_zn": {
        "hs": "7225.92",
        "name": "Flat-rolled other alloy steel, ≥600 mm, ZINC-COATED",
        "desc": "Wide flat OTHER ALLOY steel with zinc coating (HDG or EG). Key distinction from 7210 which is non-alloy.",
        "examples": "Galvanised HSLA coil, Zn-coated boron steel, galvanised dual-phase (DP) steel, Zn-coated advanced high-strength steel (AHSS)",
        "warn": "⚠️ Critical: non-alloy zinc-coated → 7210. Other ALLOY zinc-coated → 7225.92",
    },
    "r_7225_other": {
        "hs": "7225.99",
        "name": "Flat-rolled other alloy steel, ≥600 mm, other coating",
        "desc": "Other metallic or non-metallic coatings on wide flat other alloy steel.",
        "examples": "Aluminised HSLA, Galvalume alloy steel, Al-Zn coated HSLA",
        "warn": None,
    },
    "r_7226_paint": {
        "hs": "7226.93",
        "name": "Flat-rolled other alloy steel, painted/lacquered/plastic-coated",
        "desc": "Paint or plastic coating on other alloy steel flat-rolled product (narrow or wide).",
        "examples": "Pre-painted HSLA, colour-coated alloy steel strip",
        "warn": None,
    },
    "r_7226_narrow": {
        "hs": "7226",
        "name": "Flat-rolled other alloy steel, <600 mm",
        "desc": "Narrow flat other alloy steel — HR, CR, or coated. Width <600 mm.",
        "examples": "Narrow HSLA strip, narrow electrical steel strip, narrow alloy steel shim",
        "warn": None,
    },
    "r_7227": {
        "hs": "7227",
        "name": "Wire rod of other alloy steel",
        "desc": "Hot-rolled other alloy steel in coils. Feedstock for alloy steel wire.",
        "examples": "Cr-Mo wire rod, boron steel wire rod, spring steel wire rod (SAE 9254)",
        "warn": None,
    },
    "r_7228_bar": {
        "hs": "7228.10–7228.50",
        "name": "Bars and rods of other alloy steel",
        "desc": "Solid straight other alloy steel in straight lengths or coils. HR, forged, or cold-finished.",
        "examples": "4140, 4340, 4150, P20, H13, bearing steel (52100), spring steel bar",
        "warn": None,
    },
    "r_7228_sec": {
        "hs": "7228.60 / 7228.70",
        "name": "Angles, shapes and sections of other alloy steel",
        "desc": "Alloy steel structural profiles and hollow sections.",
        "examples": "Alloy steel angle, alloy hollow structural section (HSS) if not tube",
        "warn": None,
    },
    "r_7229": {
        "hs": "7229",
        "name": "Wire of other alloy steel",
        "desc": "Cold-drawn other alloy steel wire.",
        "examples": "Spring steel wire (SAE 9254), piano wire, Cr-Si valve spring wire",
        "warn": None,
    },
    "r_7301": {
        "hs": "7301",
        "name": "Sheet piling; welded angles/shapes/sections",
        "desc": "Interlocking sheet pile sections for retaining walls, cofferdams. Also welded open sections.",
        "examples": "Z-pile, U-pile, Larssen pile, combined wall sections",
        "warn": None,
    },
    "r_7302": {
        "hs": "7302",
        "name": "Railway or tramway track construction material",
        "desc": "Rails, check-rails, rack rails, switch blades, fish-plates, sole plates, rail clips.",
        "examples": "Vignoles rail, crane rail, groove rail, fish bolt and fish-plate",
        "warn": None,
    },
    "r_7304_line": {
        "hs": "7304.11 / 7304.19",
        "name": "Seamless line pipe — oil/gas/water pipelines",
        "desc": "Seamless pipes for transmission of oil, gas, or water.",
        "examples": "API 5L seamless line pipe, seamless water main pipe, X52–X70 grade",
        "warn": None,
    },
    "r_7304_octg": {
        "hs": "7304.21–7304.29",
        "name": "Seamless casing, tubing and drill pipe (OCTG)",
        "desc": "Oil country tubular goods — seamless. Casing holds wellbore; tubing carries production fluids; drill pipe transmits torque.",
        "examples": "API 5CT casing (J55, K55, N80, P110), API 5CT tubing, API 5D drill pipe",
        "warn": None,
    },
    "r_7304_mech": {
        "hs": "7304.31–7304.59",
        "name": "Seamless circular/non-circular tubes — precision/mechanical",
        "desc": "Seamless tubes for structural, mechanical, or precision applications.",
        "examples": "Hydraulic cylinder tube, boiler tube, heat exchanger tube, seamless SHS/RHS",
        "warn": None,
    },
    "r_7304_ss": {
        "hs": "7304.41–7304.49",
        "name": "Seamless tubes of stainless steel",
        "desc": "Seamless pipes and tubes of stainless steel (Cr ≥ 10.5%).",
        "examples": "SS304/316 seamless tube, stainless instrumentation tube, stainless heat exchanger tube",
        "warn": None,
    },
    "r_7304_alloy": {
        "hs": "7304.51–7304.59",
        "name": "Seamless tubes of other alloy steel",
        "desc": "Seamless pipes and tubes of other alloy steel (not stainless).",
        "examples": "Chrome-moly (P91, P22) boiler tube, alloy steel hydraulic tube, T91 superheater tube",
        "warn": None,
    },
    "r_7305": {
        "hs": "7305",
        "name": "Welded pipes/tubes, OD > 406.4 mm (large diameter)",
        "desc": "Large diameter welded pipe. Seam can be longitudinal (LSAW) or spiral (SSAW/HSAW).",
        "examples": "Large diameter API 5L welded pipe, spiral-welded pile, LSAW linepipe",
        "warn": None,
    },
    "r_7306_c": {
        "hs": "7306.10–7306.30",
        "name": "Welded pipes/tubes of non-alloy steel, OD ≤ 406.4 mm",
        "desc": "ERW or other welded non-alloy steel pipe and tube. Subheadings: line pipe / OCTG / other.",
        "examples": "ERW pipe, welded SHS/RHS/CHS (hollow section), welded boiler tube, standard pipe",
        "warn": None,
    },
    "r_7306_ss": {
        "hs": "7306.40",
        "name": "Welded tubes/pipes of stainless steel",
        "desc": "Welded stainless steel pipe and tube.",
        "examples": "Welded SS304/316 pipe, stainless sanitary tube, welded stainless ornamental tube",
        "warn": None,
    },
    "r_7306_alloy": {
        "hs": "7306.50",
        "name": "Welded tubes/pipes of other alloy steel",
        "desc": "Welded other alloy steel pipe and tube.",
        "examples": "Welded alloy steel mechanical tube, welded Cr-Mo tube",
        "warn": None,
    },
    "r_7307": {
        "hs": "7307",
        "name": "Tube or pipe fittings (elbows, flanges, couplings)",
        "desc": "Articles that connect, terminate, or change direction of pipes.",
        "examples": "Weld-neck flange, slip-on flange, butt-weld elbow (45°/90°), equal tee, reducer, coupling, union, nipple",
        "warn": None,
    },
    "r_7308": {
        "hs": "7308",
        "name": "Structures and parts of structures of iron or steel",
        "desc": "Pre-fabricated structures — cut, drilled, punched, welded — with identifiable structural function.",
        "examples": "Steel bridge span, transmission tower, scaffolding, prefab building frame, offshore jacket, door frame, warehouse portal frame",
        "warn": "⚠️ Raw section (7216) becomes 7308 once cut, drilled and assembled",
    },
    "r_7309": {
        "hs": "7309",
        "name": "Reservoirs, tanks, vats (capacity > 300 L)",
        "desc": "Large storage containers for liquids, gases, or solid goods.",
        "examples": "API 650 storage tank, above-ground fuel tank, water tower, chemical vat, silo",
        "warn": None,
    },
    "r_7310": {
        "hs": "7310",
        "name": "Tanks, drums, cans, boxes (capacity ≤ 300 L)",
        "desc": "Smaller containers — drums, jerricans, buckets, pails, tins, cans.",
        "examples": "200 L steel drum, 20 L paint tin, steel jerrican, aerosol can body",
        "warn": None,
    },
    "r_7311": {
        "hs": "7311",
        "name": "Containers for compressed or liquefied gas",
        "desc": "Pressure vessels designed for gas under pressure.",
        "examples": "LPG cylinder, CNG cylinder, oxygen/acetylene cylinder, fire extinguisher body",
        "warn": None,
    },
    "r_7312": {
        "hs": "7312",
        "name": "Stranded wire, ropes, cables, slings",
        "desc": "Multiple wires twisted or stranded together. Distinct from single wire (7217).",
        "examples": "Steel wire rope, wire strand, suspension bridge cable, lifting sling, wire hawser",
        "warn": "⚠️ Single drawn wire → 7217. Stranded/multiple wires → 7312",
    },
    "r_7313": {
        "hs": "7313",
        "name": "Barbed wire; twisted hoop or single flat wire fencing",
        "desc": "Barbed wire as a finished fencing product.",
        "examples": "Traditional 2-strand barbed wire, razor wire, concertina wire",
        "warn": None,
    },
    "r_7314": {
        "hs": "7314",
        "name": "Cloth, grill, netting, fencing, expanded metal",
        "desc": "Woven or welded wire fabric and expanded metal sheet.",
        "examples": "Welded wire mesh, chain-link fence, galvanised wire netting, expanded metal lath",
        "warn": None,
    },
    "r_7317": {
        "hs": "7317",
        "name": "Nails, tacks, drawing pins, corrugated nails, staples",
        "desc": "Small fastening devices driven in rather than screwed.",
        "examples": "Round wire nail, lost head nail, corrugated connector, staple, drawing pin, brad",
        "warn": None,
    },
    "r_7318": {
        "hs": "7318",
        "name": "Screws, bolts, nuts, rivets, washers and similar fasteners",
        "desc": "Threaded and non-threaded fasteners for joining structural elements.",
        "examples": "Hex bolt (M12–M36), hex nut, coach screw, anchor bolt, pop rivet, spring washer, flat washer, cotter pin",
        "warn": None,
    },
    "r_7320": {
        "hs": "7320",
        "name": "Springs and leaves for springs",
        "desc": "Elastic energy storage devices — leaf, coil, torsion, disc springs.",
        "examples": "Parabolic leaf spring (truck), coil spring (suspension/industrial), torsion bar, Belleville disc spring",
        "warn": "⚠️ Wire coil (before forming) → 7217. Completed spring → 7320",
    },
    "r_7321": {
        "hs": "7321",
        "name": "Stoves, ranges, cookers, barbecues, braziers, gas rings",
        "desc": "Domestic or commercial appliances for cooking or room heating.",
        "examples": "Cast iron wood-burning stove, gas cooker body, barbecue grill body, pellet stove",
        "warn": None,
    },
    "r_7322": {
        "hs": "7322",
        "name": "Radiators for central heating; air heaters",
        "desc": "Space heating equipment with fluid or air circulation.",
        "examples": "Steel panel radiator, cast iron column radiator, industrial warm air distributor",
        "warn": None,
    },
    "r_7323": {
        "hs": "7323",
        "name": "Table, kitchen or household articles; pot scourers, steel wool",
        "desc": "Domestic use in kitchen, dining, or household setting.",
        "examples": "Saucepan, stockpot, wok, baking tray, colander, kitchen rack, dustbin, bucket, steel wool pad",
        "warn": None,
    },
    "r_7324": {
        "hs": "7324",
        "name": "Sanitary ware and parts thereof",
        "desc": "Plumbing and bathroom sanitary fixtures.",
        "examples": "Steel bath tub, pressed steel sink, bidet, shower tray",
        "warn": None,
    },
    "r_7326": {
        "hs": "7326",
        "name": "Other articles of iron or steel (residual)",
        "desc": "Catch-all for fabricated steel articles not classified elsewhere in Chapter 73.",
        "examples": "Steel cable tray, steel anchor, belt buckle, horseshoe, shop sign bracket, steel lock body",
        "warn": "⚠️ Use only when no more specific 73xx heading applies",
    },
}

# ─────────────────────────────────────────────
#  SESSION STORAGE  (in-memory, per chat_id)
# ─────────────────────────────────────────────

sessions: dict[int, dict] = {}

def get_session(chat_id: int) -> dict:
    if chat_id not in sessions:
        sessions[chat_id] = {"node": "start", "history": []}
    return sessions[chat_id]

def reset_session(chat_id: int):
    sessions[chat_id] = {"node": "start", "history": []}

# ─────────────────────────────────────────────
#  KEYBOARD BUILDERS
# ─────────────────────────────────────────────

def build_keyboard(node_id: str) -> InlineKeyboardMarkup:
    node = TREE.get(node_id)
    if not node:
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Restart", callback_data="__restart__")]])
    buttons = []
    for i, (label, _) in enumerate(node["opts"]):
        short = label[:55] + "…" if len(label) > 56 else label
        buttons.append([InlineKeyboardButton(short, callback_data=f"opt_{i}")])
    buttons.append([InlineKeyboardButton("🔄 Restart", callback_data="__restart__")])
    return InlineKeyboardMarkup(buttons)

def result_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 Classify another item", callback_data="__restart__")]
    ])

# ─────────────────────────────────────────────
#  MESSAGE BUILDERS
# ─────────────────────────────────────────────

def node_message(node_id: str, history: list) -> str:
    node = TREE.get(node_id)
    if not node:
        return "❌ Unknown node. Please restart."
    parts = []
    if history:
        trail = " › ".join(f"*{h['ans'][:30]}*" for h in history[-3:])
        parts.append(f"_Path: {trail}_\n")
    parts.append(node["q"])
    if node.get("hint"):
        parts.append(f"\n💡 _{node['hint']}_")
    return "\n".join(parts)

def result_message(result_id: str) -> str:
    r = RESULTS.get(result_id)
    if not r:
        return "❌ Result not found."
    lines = [
        f"✅ *Classification Result*\n",
        f"📦 *HS Heading: {r['hs']}*",
        f"_{r['name']}_\n",
        f"{r['desc']}\n",
        f"*Typical examples:*\n{r['examples']}",
    ]
    if r.get("warn"):
        lines.append(f"\n{r['warn']}")
    return "\n".join(lines)

# ─────────────────────────────────────────────
#  HANDLERS
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reset_session(chat_id)
    session = get_session(chat_id)
    text = (
        "👋 *Welcome to the HS 72/73 Classifier Bot*\n\n"
        "I will guide you through a step-by-step decision tree to find the correct "
        "HS heading for iron and steel products (Chapters 72 & 73).\n\n"
        "Tap an option below to begin:"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=build_keyboard(session["node"]),
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*HS 72/73 Classifier Bot — Help*\n\n"
        "• /start — begin a new classification\n"
        "• /restart — restart from the beginning\n"
        "• /about — about this bot\n\n"
        "Answer each question by tapping a button. "
        "The bot will walk you through the full decision tree and return the HS heading with examples.",
        parse_mode="Markdown",
    )

async def about_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*HS 72/73 Classifier Bot*\n\n"
        "Covers all HS headings 7201–7229 (Chapter 72 — Iron & Steel material) "
        "and 7301–7326 (Chapter 73 — Articles of Iron or Steel).\n\n"
        "Includes detailed subheadings for:\n"
        "• Flat-rolled products (width test, coating type, rolling method)\n"
        "• Zinc-coated alloy steel (7225.92) vs non-alloy (7210)\n"
        "• Seamless vs welded pipes (7304–7306)\n"
        "• All long products, sections, wire\n"
        "• All Chapter 73 finished articles\n\n"
        "_Based on WCO Harmonized System nomenclature._",
        parse_mode="Markdown",
    )

async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    reset_session(chat_id)
    session = get_session(chat_id)
    await update.message.reply_text(
        "🔄 Restarted. Let's classify from the beginning:",
        parse_mode="Markdown",
        reply_markup=build_keyboard(session["node"]),
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    data = query.data

    if data == "__restart__":
        reset_session(chat_id)
        session = get_session(chat_id)
        await query.edit_message_text(
            "🔄 Restarted. Let's classify from the beginning:\n\n" + node_message(session["node"], []),
            parse_mode="Markdown",
            reply_markup=build_keyboard(session["node"]),
        )
        return

    session = get_session(chat_id)
    current = session["node"]
    node = TREE.get(current)

    if not node or not data.startswith("opt_"):
        await query.edit_message_text("❌ Session error. Use /start to restart.")
        return

    idx = int(data.split("_")[1])
    if idx >= len(node["opts"]):
        await query.edit_message_text("❌ Invalid option. Use /start to restart.")
        return

    label, next_node = node["opts"][idx]
    session["history"].append({"q": node["q"], "ans": label, "from": current})
    session["node"] = next_node

    if next_node in RESULTS:
        await query.edit_message_text(
            result_message(next_node),
            parse_mode="Markdown",
            reply_markup=result_keyboard(),
        )
    elif next_node in TREE:
        await query.edit_message_text(
            node_message(next_node, session["history"]),
            parse_mode="Markdown",
            reply_markup=build_keyboard(next_node),
        )
    else:
        await query.edit_message_text(
            f"❌ Unknown node: {next_node}. Use /start to restart."
        )

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
