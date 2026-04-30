from __future__ import annotations

import csv
import difflib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


OUTPUT_JSON = Path(".sisyphus/tmp/corpus_candidates.json")


TITLES = [
    {"tier": "tier1", "title": "VizWiz: nearly real-time answers to visual questions"},
    {"tier": "tier1", "title": "VizWiz Grand Challenge: Answering Visual Questions from Blind People"},
    {"tier": "tier1", "title": "Crowdsourcing subjective fashion advice using VizWiz: challenges and opportunities"},
    {"tier": "tier1", "title": '"Person, Shoes, Tree. Is the Person Naked?" What People with Vision Impairments Want in Image Descriptions'},
    {"tier": "tier1", "title": "Going beyond one-size-fits-all image descriptions to satisfy the information wants of people who are blind or have low vision"},
    {"tier": "tier1", "title": '"It\'s complicated": Negotiating accessibility and (mis) representation in image descriptions of race, gender, and disability'},
    {"tier": "tier1", "title": "The emerging professional practice of remote sighted assistance for people with visual impairments"},
    {"tier": "tier1", "title": "Are Two Heads Better than One? Investigating Remote Sighted Assistance with Paired Volunteers"},
    {"tier": "tier1", "title": "Human–AI Collaboration for Remote Sighted Assistance: Perspectives from the LLM Era"},
    {"tier": "tier1", "title": "Investigating Use Cases of AI-Powered Scene Description Applications for Blind and Low Vision People"},
    {"tier": "tier1", "title": "Beyond Visual Perception: Insights from Smartphone Interaction of Visually Impaired Users with Large Multimodal Models"},
    {"tier": "tier1", "title": "Evaluation and comparison of artificial intelligence vision aids: Orcam myeye 1 and seeing ai"},
    {"tier": "tier1", "title": "Recog: Supporting blind people in recognizing personal objects"},
    {"tier": "tier1", "title": "Understanding Personalized Accessibility through Teachable AI: Designing and Evaluating Find My Things for People who are Blind or Low Vision"},
    {"tier": "tier1", "title": "Blind Users Accessing Their Training Images in Teachable Object Recognizers"},
    {"tier": "tier1", "title": "Audio Description Customization"},
    {"tier": "tier1", "title": "Helping Helpers: Supporting Volunteers in Remote Sighted Assistance with Augmented Reality Maps"},
    {"tier": "tier1", "title": "BubbleCam: Engaging Privacy in Remote Sighted Assistance"},
    {"tier": "tier1", "title": "Iterative Design and Prototyping of Computer Vision Mediated Remote Sighted Assistance"},
    {"tier": "tier1", "title": "A system for remote sighted guidance of visually impaired pedestrians"},
    {"tier": "tier1", "title": "Tele-guidance based navigation system for the visually impaired and blind persons"},
    {"tier": "tier1", "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"},
    {"tier": "tier1", "title": "Dense Passage Retrieval for Open-Domain Question Answering"},
    {"tier": "tier1", "title": "REALM: Retrieval-Augmented Language Model Pre-Training"},
    {"tier": "tier1", "title": "Language Models that Seek for Knowledge: Modular Search & Generation for Dialogue and Prompt Completion"},
    {"tier": "tier1", "title": "MemoryBank: Enhancing Large Language Models with Long-Term Memory"},
    {"tier": "tier1", "title": "Making conversations with chatbots more personalized"},
    {"tier": "tier1", "title": "What is personalization? Perspectives on the design and implementation of personalization in information systems"},
    {"tier": "tier1", "title": "An introduction to personalization and mass customization"},
    {"tier": "tier1", "title": "A user-centered design approach to personalization"},
    {"tier": "tier1", "title": "Personality-Driven Decision Making in LLM-Based Autonomous Agents"},
    {"tier": "tier1", "title": "Does your AI agent get you? A personalizable framework for approximating human models from argumentation-based dialogue traces"},
    {"tier": "tier1", "title": "Navigating the Unknown: A Chat-Based Collaborative Interface for Personalized Exploratory Tasks"},
    {"tier": "tier2", "title": "A Prompt Chaining Framework for Long-Term Recall in LLM-Powered Intelligent Assistant"},
    {"tier": "tier2", "title": "Visual Question Answering"},
    {"tier": "tier2", "title": "Making the V in VQA Matter: Elevating the Role of Image Understanding in Visual Question Answering"},
    {"tier": "tier2", "title": "LXMERT: Learning Cross-Modality Encoder Representations from Transformers"},
    {"tier": "tier2", "title": "VilBERT: Pretraining Task-Agnostic Visiolinguistic Representations for Vision-and-Language Tasks"},
    {"tier": "tier2", "title": "VL-BERT: Pre-training of Generic Visual-Linguistic Representations"},
    {"tier": "tier2", "title": "UNITER: Learning UNiversal Image-Text Representations"},
    {"tier": "tier2", "title": "Oscar: Object-Semantics Aligned Pre-training for Vision-Language Tasks"},
    {"tier": "tier2", "title": "Cross-Modal Self-Attention Network for Referring Image Segmentation"},
    {"tier": "tier2", "title": "VideoBERT: A Joint Model for Video and Language Representation Learning"},
    {"tier": "tier3", "title": "Attention Is All You Need"},
    {"tier": "tier3", "title": "An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale"},
    {"tier": "tier3", "title": "Training data-efficient image transformers & distillation through attention"},
    {"tier": "tier3", "title": "End-to-End Object Detection with Transformers"},
    {"tier": "tier3", "title": "Deformable DETR: Deformable Transformers for End-to-End Object Detection"},
    {"tier": "tier3", "title": "Non-local Neural Networks"},
    {"tier": "tier3", "title": "Stand-Alone Self-Attention in Vision Models"},
    {"tier": "tier3", "title": "Attention Augmented Convolutional Networks"},
]


ALLOWED_TYPES = {"journal-article", "proceedings-article", "book-chapter"}


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "ally-vision-v2-corpus-builder/1.0 (contact: local-script)"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("–", "-").replace("—", "-").split())


def best_match(title: str, items: list[dict]) -> dict | None:
    target = normalize(title)
    ranked: list[tuple[float, dict]] = []
    for item in items:
        item_titles = item.get("title") or []
        if not item_titles:
            continue
        candidate = normalize(item_titles[0])
        score = difflib.SequenceMatcher(a=target, b=candidate).ratio()
        type_ok = item.get("type") in ALLOWED_TYPES
        if type_ok:
            score += 0.05
        ranked.append((score, item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1] if ranked else None


def author_string(item: dict) -> str:
    authors = []
    for a in item.get("author", []):
        given = a.get("given", "").strip()
        family = a.get("family", "").strip()
        name = " ".join(part for part in (given, family) if part)
        if name:
            authors.append(name)
    return "; ".join(authors)


def venue_string(item: dict) -> str:
    container = item.get("container-title") or []
    if container:
        return container[0]
    return item.get("publisher", "")


def year_value(item: dict) -> int | None:
    for key in ("published-print", "published-online", "issued"):
        block = item.get(key) or {}
        parts = block.get("date-parts") or []
        if parts and parts[0]:
            return parts[0][0]
    return None


def doi_url(item: dict) -> str:
    doi = item.get("DOI")
    if doi:
        return f"https://doi.org/{doi}"
    return item.get("URL", "")


def main() -> int:
    results = []
    for entry in TITLES:
        title = entry["title"]
        query = urllib.parse.quote(title)
        data = fetch_json(f"https://api.crossref.org/works?query.title={query}&rows=5")
        items = data.get("message", {}).get("items", [])
        match = best_match(title, items)
        result = {
            "requested_title": title,
            "tier": entry["tier"],
            "matched": bool(match),
        }
        if match:
            result.update(
                {
                    "matched_title": (match.get("title") or [""])[0],
                    "type": match.get("type", ""),
                    "year": year_value(match),
                    "venue": venue_string(match),
                    "doi_or_url": doi_url(match),
                    "authors": author_string(match),
                }
            )
        results.append(result)
        time.sleep(0.3)

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(results)} candidate lookups to {OUTPUT_JSON}")
    unmatched = [r for r in results if not r["matched"]]
    if unmatched:
        print("Unmatched titles:")
        for row in unmatched:
            print(f"- {row['requested_title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
