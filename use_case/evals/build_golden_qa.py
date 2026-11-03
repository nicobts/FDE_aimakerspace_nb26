"""Build golden_qa.jsonl: one reference answer per labelled question in retrieval.jsonl.

The references are written from the gold papers' abstracts: each cites every gold paper and
states the reviewed facts, so the oracle meets the definition of "correct" the scorers check.
golden.jsonl stays the Week 1 card goldens, because 02_Open_Weights/challenge/generate.py reads
it as card examples. Rerun after editing REFERENCES or adding labels:

    python use_case/evals/build_golden_qa.py
"""

import json
from pathlib import Path

HERE = Path(__file__).parent

REFERENCES = {
    "q01": "In the study that roasted to SCA roast levels, medium roast developed pleasant notes such as sweet, toasted hazelnut and caramel, while the extremely dark roast developed off-notes: burnt, putrid and sulfurous [W4403193476].",
    "q02": "Anaerobic in-cherry fermentation changes the green coffee's precursors (reducing sugars, amino acids, organic acids) and raises fermentation-derived fruity esters, mainly ethyl and acetate esters, which carry the fruity notes into the roasted coffee [W7221334596].",
    "q03": "No: nello studio l'ocratossina è rimasta simile (circa 2,9-3,5 µg/kg) con fermentazione prolungata fino a 20 ore e ritardi di lavorazione fino a 48 ore; conta di più eliminare i frutti secchi e difettosi prima dell'essiccazione [W7127046736].",
    "q04": "On the farm, good agricultural and post-harvest practices limit the fungi that produce ochratoxin A; during processing, biocontrol with lactic acid bacteria, yeasts and fungi can adsorb or degrade it [W4401894533], and wild yeasts added during fermentation inhibited the germination of ochratoxin-producing fungi [W4405184446].",
    "q05": "Castillo coped better with drought than Caturra: it kept leaf water potential and gas exchange longer, while Caturra closed its stomata earlier; both tolerated the heat, and both varieties recovered their physiological values after rewatering [W7164393911].",
    "q06": "It depends on the species and the region: in Uganda, agroforestry with up to 50% shade could offset suitable-area losses for robusta but not for arabica [W4400295494], while in Rwanda a shade-tree corridor was found feasible to protect coffee areas under climate change [W4412463026].",
    "q07": "Roasted coffee in aluminium bags kept its quality for about 250 days at 20 °C, longer when cooler [W4415616418]; in compostable capsules the bioplastic lets moisture in, and under hot, humid storage the critical moisture level that triggers quality decay was reached within three weeks [W4404705896].",
    "q08": "Pasteurised cold brew made from medium or dark roasted beans stayed microbiologically stable for 150 days at 4 °C, while the one from light roasted beans failed earlier, so the roast level matters [W4406429231].",
    "q09": "Yes: a survey of German consumers found a willingness to pay more for coffee whose sustainability certification is backed by blockchain-based digital traceability, shaped by perceived behavioural control and social norms [W7161753552].",
    "q11": "Takeaway coffees contained on average about three times more caffeine than homemade ones, with large differences by type (for example americano versus espresso); drinking 3-5 takeaway coffees a day can exceed the 400 mg safe daily intake, while homemade coffees mostly stay below it [W4400906101].",
    "q12": "Yes: a proposed system films the crema, segments it with the GrabCut algorithm and uses clustering on its features to set the brewing conditions for each cup in real time [W4391962816].",
    "q13": "Cascara has been made into an edible coating that extended the shelf life of roasted hazelnuts [W4402301389]; spent coffee grounds and silverskin contain dietary fibre, proteins, lipids, minerals, caffeine, chlorogenic acids and other polyphenols, which makes them food and nutraceutical ingredients [W4392711737].",
    "u01": "Conta l'alcalinità, non la durezza: il bicarbonato, fino a 300 mg/L nell'esperimento, riduce acidità, note fruttate e complessità e aumenta le note tostate e amare, mentre il calcio da solo non cambia in modo marcato il gusto [W7213286814].",
    "u02": "PFAS were found in brewed capsule coffee: perfluorooctanoic acid and 8:2 fluorotelomer sulfonate were higher when capsules were brewed by machine than by hand through a paper filter, but the hazard quotient and cancer risk stayed below WHO limits [W4408403534].",
    "u03": "Heating the beans just before grinding lowered caffeine and chlorogenic acids and shifted the aroma towards ageing, with more hexanal; cooling had similar but smaller effects and reduced caffeine extraction [W7161248227].",
    "u04": "NIR spectroscopy separated light, medium and dark roasts as well as GC-MS did, and a PLS model on NIR spectra predicted over 20 volatile compounds, including furans, ketones, phenols and pyridines, with R² above 0.75, so it can complement GC-MS on the line [W4390748041].",
    "u05": "Yes: low-temperature long-time (LTLT) roasting kept chlorogenic acids at about 9.4-9.6 g/kg, similar to a medium roast, while high-temperature short-time (HTST) roasting caused the largest loss, about 60-75% [W7171390324].",
}
DECLINE_REASON = ("The corpus holds published papers only; the company's own blends and internal lab results are "
                  "not in it, so no figure can be given.")


def main():
    rows = [json.loads(line) for line in (HERE / "retrieval.jsonl").read_text(encoding="utf-8").splitlines()[1:] if line.strip()]
    out = []
    for label in rows:
        if label["kind"] == "decline":
            reference = {"needs_human": True, "needs_human_reason": DECLINE_REASON, "answer": None, "sources": [], "retrieved": []}
        else:
            text = REFERENCES[label["id"]]
            missing = [t for t in label["expected_terms"] if t.lower() not in text.lower()] + [g for g in label["gold"] if g not in text]
            if missing:
                raise SystemExit(f"{label['id']}: reference misses {missing}")
            reference = {"needs_human": False, "needs_human_reason": None, "answer": text, "sources": label["gold"], "retrieved": label["gold"]}
        out.append({"id": label["id"], "input": label["question"], "output": json.dumps(reference, ensure_ascii=False),
                    "kind": label["kind"], "gold": label["gold"], "expected_terms": label["expected_terms"],
                    "why": "reference written from the gold abstracts; " + label["source"]})
    (HERE / "golden_qa.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8")
    print(f"{len(out)} QA goldens written")


if __name__ == "__main__":
    main()
