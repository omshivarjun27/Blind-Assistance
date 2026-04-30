from __future__ import annotations

import csv
import html
import json
from pathlib import Path


ROOT = Path('.')
LOOKUP_JSON = ROOT / '.sisyphus' / 'tmp' / 'corpus_candidates.json'
CSV_PATH = ROOT / 'docs' / 'Survey paper' / 'literature_corpus.csv'
BIB_PATH = ROOT / 'docs' / 'Survey paper' / 'references.bib'


def clean_text(text: str) -> str:
    return html.unescape(text).replace('–', '-').replace('—', '-').replace('“', '"').replace('”', '"').replace('’', "'")


def load_lookup() -> dict[str, dict]:
    rows = json.loads(LOOKUP_JSON.read_text(encoding='utf-8'))
    return {row['requested_title']: row for row in rows}


GOOD_TITLES = [
    ('tier1', 'VizWiz Grand Challenge: Answering Visual Questions from Blind People', 'gurari2018vizwiz', 'Blind-user visual question answering benchmark and dataset for accessible scene-query systems.'),
    ('tier1', 'Crowdsourcing subjective fashion advice using VizWiz: challenges and opportunities', 'burton2012vizwizfashion', 'Blind-user fashion assistance study that informs subjective visual feedback boundaries.'),
    ('tier1', '"Person, Shoes, Tree. Is the Person Naked?" What People with Vision Impairments Want in Image Descriptions', 'stangl2020personshoes', 'Direct evidence on what blind users want from image descriptions.'),
    ('tier1', 'Going beyond one-size-fits-all image descriptions to satisfy the information wants of people who are blind or have low vision', 'stangl2021onesize', 'User-specific description preferences relevant to adaptive visual assistance.'),
    ('tier1', '"It\'s complicated": Negotiating accessibility and (mis) representation in image descriptions of race, gender, and disability', 'bennett2021complicated', 'Identity-description risk analysis directly relevant to sensitive multimodal assistance.'),
    ('tier1', 'The emerging professional practice of remote sighted assistance for people with visual impairments', 'lee2020rsa', 'Grounding paper for remote sighted assistance workflows and handoff design.'),
    ('tier1', 'Are Two Heads Better than One? Investigating Remote Sighted Assistance with Paired Volunteers', 'xie2023twoheads', 'Explores multi-helper coordination patterns for blind assistance tasks.'),
    ('tier1', 'Human–AI Collaboration for Remote Sighted Assistance: Perspectives from the LLM Era', 'yu2024humanai', 'LLM-era framing for remote assistance and human-AI collaboration.'),
    ('tier1', 'Investigating Use Cases of AI-Powered Scene Description Applications for Blind and Low Vision People', 'gonzalez2024scene', 'Empirical usage patterns for modern AI scene-description tools.'),
    ('tier1', 'Beyond Visual Perception: Insights from Smartphone Interaction of Visually Impaired Users with Large Multimodal Models', 'xie2025beyond', 'Recent CHI evidence on LMM-based assistance strengths and failure modes for visually impaired users.'),
    ('tier1', 'Evaluation and comparison of artificial intelligence vision aids: Orcam myeye 1 and seeing ai', 'granquist2021visionaids', 'Compares deployed visual aids and helps position Ally Vision against existing assistive tools.'),
    ('tier1', 'Recog: Supporting blind people in recognizing personal objects', 'ahmetovic2020recog', 'Personal-object recognition assistance relevant to scene and object understanding.'),
    ('tier1', 'Understanding Personalized Accessibility through Teachable AI: Designing and Evaluating Find My Things for People who are Blind or Low Vision', 'morrison2023findmythings', 'Personalized teachable-AI framing for blind-accessibility workflows.'),
    ('tier1', 'Blind Users Accessing Their Training Images in Teachable Object Recognizers', 'hong2022trainingimages', 'Blind-user interaction evidence for object recognizers and teachable vision systems.'),
    ('tier1', 'Audio Description Customization', 'natalie2024audiodescription', 'Customization paper relevant to adaptive spoken output and user preference handling.'),
    ('tier1', 'Helping Helpers: Supporting Volunteers in Remote Sighted Assistance with Augmented Reality Maps', 'xie2022helpinghelpers', 'Helper-support design for remote visual assistance and collaborative guidance.'),
    ('tier1', 'BubbleCam: Engaging Privacy in Remote Sighted Assistance', 'xie2024bubblecam', 'Privacy-sensitive assistance design relevant to camera-mediated support.'),
    ('tier1', 'Iterative Design and Prototyping of Computer Vision Mediated Remote Sighted Assistance', 'xie2022iterative', 'Design history of computer-vision-mediated remote assistance systems.'),
    ('tier1', 'A system for remote sighted guidance of visually impaired pedestrians', 'garaj2003sightedguidance', 'Early remote-guidance system paper for navigation assistance.'),
    ('tier1', 'Tele-guidance based navigation system for the visually impaired and blind persons', 'chaudary2017teleguidance', 'Navigation-specific tele-guidance system relevant to on-demand visual assistance.'),
    ('tier1', 'Dense Passage Retrieval for Open-Domain Question Answering', 'karpukhin2020dpr', 'Dense retrieval foundation directly relevant to memory recall and document retrieval components.'),
    ('tier1', 'Language Models that Seek for Knowledge: Modular Search & Generation for Dialogue and Prompt Completion', 'shuster2022seekknowledge', 'Dialogue-focused retrieval plus generation design relevant to modular assistive agents.'),
    ('tier1', 'MemoryBank: Enhancing Large Language Models with Long-Term Memory', 'zhong2024memorybank', 'Peer-reviewed long-term memory design for personalized conversational systems.'),
    ('tier1', 'Making conversations with chatbots more personalized', 'shumanov2021chatbots', 'Measured personalization benefits in chatbot interactions.'),
    ('tier1', 'What is personalization? Perspectives on the design and implementation of personalization in information systems', 'fan2006personalization', 'Conceptual grounding for defining personalization in the journal paper framing.'),
    ('tier1', 'An introduction to personalization and mass customization', 'tiihonen2017personalization', 'System-level personalization framing relevant to user-adaptive assistance.'),
    ('tier1', 'Personality-Driven Decision Making in LLM-Based Autonomous Agents', 'newsham2025personality', 'Peer-reviewed agent personalization evidence for decision behavior and user modeling.'),
    ('tier1', 'Does your AI agent get you? A personalizable framework for approximating human models from argumentation-based dialogue traces', 'tang2025personalizable', 'Personalizable-agent framework relevant to user profile and adaptation design.'),
    ('tier1', 'Navigating the Unknown: A Chat-Based Collaborative Interface for Personalized Exploratory Tasks', 'peng2025navigating', 'Personalized chat-interface design relevant to human-centered exploration assistance.'),
    ('tier1', 'A Prompt Chaining Framework for Long-Term Recall in LLM-Powered Intelligent Assistant', 'seo2025promptchaining', 'Long-term recall mechanism relevant to persistent memory and retrieval orchestration.'),
    ('tier2', 'Making the V in VQA Matter: Elevating the Role of Image Understanding in Visual Question Answering', 'goyal2019vqamatter', 'Stronger image-understanding baseline for visual question answering quality.'),
    ('tier2', 'LXMERT: Learning Cross-Modality Encoder Representations from Transformers', 'tan2019lxmert', 'Canonical multimodal transformer for vision-language representation learning.'),
    ('tier2', 'UNITER: Learning UNiversal Image-Text Representations', 'chen2020uniter', 'Unified image-text representation learning for multimodal fusion.'),
    ('tier2', 'Oscar: Object-Semantics Aligned Pre-training for Vision-Language Tasks', 'li2020oscar', 'Object-semantics aligned multimodal pretraining relevant to scene-grounded reasoning.'),
    ('tier2', 'Cross-Modal Self-Attention Network for Referring Image Segmentation', 'ye2019cmsa', 'Cross-modal attention design relevant to image-text grounding.'),
    ('tier2', 'VideoBERT: A Joint Model for Video and Language Representation Learning', 'sun2019videobert', 'Multimodal transformer example for long-range audio-visual representation learning.'),
    ('tier2', 'Non-local Neural Networks', 'wang2018nonlocal', 'Long-range dependency modeling relevant to scene understanding architectures.'),
    ('tier2', 'Attention Augmented Convolutional Networks', 'bello2019attentionaugmented', 'Hybrid attention-convolution design relevant to efficient visual perception.'),
]


MANUAL_ENTRIES = [
    {
        'tier': 'tier1',
        'title': 'VizWiz',
        'ref_key': 'bigham2010vizwiz',
        'authors': 'Jeffrey P. Bigham; Chandrika Jayant; Hanjie Ji; Greg Little; Andrew Miller; Robert C. Miller; Robin Miller; Aubrey Tatarowicz; Brandyn White; Samual White; Tom Yeh',
        'year': 2010,
        'venue': 'Proceedings of the 23nd annual ACM symposium on User interface software and technology',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://doi.org/10.1145/1866029.1866080',
        'abstract_url': 'https://doi.org/10.1145/1866029.1866080',
        'method_url': 'https://doi.org/10.1145/1866029.1866080',
        'relevance_note': 'Early blind-user visual question workflow that motivates accessible image-query interaction.',
        'entry_type': 'inproceedings',
        'booktitle': 'Proceedings of the 23nd annual ACM symposium on User interface software and technology',
        'url': 'https://doi.org/10.1145/1866029.1866080',
    },
    {
        'tier': 'tier1',
        'title': 'Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks',
        'ref_key': 'lewis2020rag',
        'authors': 'Patrick Lewis; Ethan Perez; Aleksandra Piktus; Fabio Petroni; Vladimir Karpukhin; Naman Goyal; Heinrich Kuttler; Mike Lewis; Wen-tau Yih; Tim Rocktaschel; Sebastian Riedel; Douwe Kiela',
        'year': 2020,
        'venue': 'Advances in Neural Information Processing Systems 33',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html',
        'abstract_url': 'https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html',
        'method_url': 'https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html',
        'relevance_note': 'Foundational retrieval-augmented generation paper for memory-backed assistive dialogue.',
        'entry_type': 'inproceedings',
        'booktitle': 'Advances in Neural Information Processing Systems 33',
        'url': 'https://proceedings.neurips.cc/paper/2020/hash/6b493230205f780e1bc26945df7481e5-Abstract.html',
    },
    {
        'tier': 'tier1',
        'title': 'REALM: Retrieval-Augmented Language Model Pre-Training',
        'ref_key': 'guu2020realm',
        'authors': 'Kelvin Guu; Kenton Lee; Zora Tung; Panupong Pasupat; Ming-Wei Chang',
        'year': 2020,
        'venue': 'Proceedings of the 37th International Conference on Machine Learning',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://proceedings.mlr.press/v119/guu20a.html',
        'abstract_url': 'https://proceedings.mlr.press/v119/guu20a.html',
        'method_url': 'https://proceedings.mlr.press/v119/guu20a.html',
        'relevance_note': 'Retriever-pretraining foundation for modular knowledge access in assistive agents.',
        'entry_type': 'inproceedings',
        'booktitle': 'Proceedings of the 37th International Conference on Machine Learning',
        'url': 'https://proceedings.mlr.press/v119/guu20a.html',
    },
    {
        'tier': 'tier2',
        'title': 'Visual Question Answering',
        'ref_key': 'antol2015vqa',
        'authors': 'Stanislaw Antol; Aishwarya Agrawal; Jiasen Lu; Margaret Mitchell; Dhruv Batra; C. Lawrence Zitnick; Devi Parikh',
        'year': 2015,
        'venue': 'Proceedings of the IEEE International Conference on Computer Vision (ICCV)',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://openaccess.thecvf.com/content_iccv_2015/html/Antol_VQA_Visual_Question_ICCV_2015_paper.html',
        'abstract_url': 'https://openaccess.thecvf.com/content_iccv_2015/html/Antol_VQA_Visual_Question_ICCV_2015_paper.html',
        'method_url': 'https://openaccess.thecvf.com/content_iccv_2015/html/Antol_VQA_Visual_Question_ICCV_2015_paper.html',
        'relevance_note': 'Core visual question answering benchmark paper that explicitly names visually impaired assistance as a motivating scenario.',
        'entry_type': 'inproceedings',
        'booktitle': 'Proceedings of the IEEE International Conference on Computer Vision (ICCV)',
        'url': 'https://openaccess.thecvf.com/content_iccv_2015/html/Antol_VQA_Visual_Question_ICCV_2015_paper.html',
    },
    {
        'tier': 'tier2',
        'title': 'Unicoder-VL: A Universal Encoder for Vision and Language by Cross-modal Pre-training',
        'ref_key': 'li2020unicodervl',
        'authors': 'Gen Li; Nan Duan; Yuejian Fang; Ming Gong; Daxin Jiang',
        'year': 2020,
        'venue': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://doi.org/10.1609/aaai.v34i07.6795',
        'abstract_url': 'https://doi.org/10.1609/aaai.v34i07.6795',
        'method_url': 'https://doi.org/10.1609/aaai.v34i07.6795',
        'relevance_note': 'Cross-modal pretraining paper relevant to multimodal fusion and representation transfer.',
        'entry_type': 'article',
        'journal': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'doi': '10.1609/aaai.v34i07.6795',
    },
    {
        'tier': 'tier2',
        'title': 'Unified Vision-Language Pre-training for Image Captioning and VQA',
        'ref_key': 'zhou2020unifiedvlp',
        'authors': 'Luowei Zhou; Hamid Palangi; Lei Zhang; Houdong Hu; Jason Corso; Jianfeng Gao',
        'year': 2020,
        'venue': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://doi.org/10.1609/aaai.v34i07.7005',
        'abstract_url': 'https://doi.org/10.1609/aaai.v34i07.7005',
        'method_url': 'https://doi.org/10.1609/aaai.v34i07.7005',
        'relevance_note': 'Unified vision-language pretraining paper relevant to joint captioning and question answering design.',
        'entry_type': 'article',
        'journal': 'Proceedings of the AAAI Conference on Artificial Intelligence',
        'doi': '10.1609/aaai.v34i07.7005',
    },
    {
        'tier': 'tier2',
        'title': 'Learning Texture Transformer Network for Image Super-Resolution',
        'ref_key': 'yang2020ttsr',
        'authors': 'Fuzhi Yang; Huan Yang; Jianlong Fu; Hongtao Lu; Baining Guo',
        'year': 2020,
        'venue': '2020 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://doi.org/10.1109/cvpr42600.2020.00583',
        'abstract_url': 'https://doi.org/10.1109/cvpr42600.2020.00583',
        'method_url': 'https://doi.org/10.1109/cvpr42600.2020.00583',
        'relevance_note': 'Transformer-based visual restoration paper relevant to image-quality and perceptual modeling.',
        'entry_type': 'inproceedings',
        'booktitle': '2020 IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)',
        'doi': '10.1109/cvpr42600.2020.00583',
    },
    {
        'tier': 'tier3',
        'title': 'Attention Is All You Need',
        'ref_key': 'vaswani2017attention',
        'authors': 'Ashish Vaswani; Noam Shazeer; Niki Parmar; Jakob Uszkoreit; Llion Jones; Aidan N. Gomez; Lukasz Kaiser; Illia Polosukhin',
        'year': 2017,
        'venue': 'Advances in Neural Information Processing Systems 30',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://proceedings.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html',
        'abstract_url': 'https://proceedings.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html',
        'method_url': 'https://proceedings.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html',
        'relevance_note': 'Foundational transformer architecture paper underlying the multimodal stack discussed across the survey.',
        'entry_type': 'inproceedings',
        'booktitle': 'Advances in Neural Information Processing Systems 30',
        'url': 'https://proceedings.neurips.cc/paper_files/paper/2017/hash/3f5ee243547dee91fbd053c1c4a845aa-Abstract.html',
    },
    {
        'tier': 'tier3',
        'title': 'An Image is Worth 16x16 Words: Transformers for Image Recognition at Scale',
        'ref_key': 'dosovitskiy2021vit',
        'authors': 'Alexey Dosovitskiy; Lucas Beyer; Alexander Kolesnikov; Dirk Weissenborn; Xiaohua Zhai; Thomas Unterthiner; Mostafa Dehghani; Matthias Minderer; Georg Heigold; Sylvain Gelly; Jakob Uszkoreit; Neil Houlsby',
        'year': 2021,
        'venue': 'International Conference on Learning Representations',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://openreview.net/forum?id=YicbFdNTTy',
        'abstract_url': 'https://openreview.net/forum?id=YicbFdNTTy',
        'method_url': 'https://openreview.net/forum?id=YicbFdNTTy',
        'relevance_note': 'Canonical vision-transformer paper used as a foundational reference for modern visual attention systems.',
        'entry_type': 'inproceedings',
        'booktitle': 'International Conference on Learning Representations',
        'url': 'https://openreview.net/forum?id=YicbFdNTTy',
    },
    {
        'tier': 'tier3',
        'title': 'Training data-efficient image transformers & distillation through attention',
        'ref_key': 'touvron2021deit',
        'authors': 'Hugo Touvron; Matthieu Cord; Matthijs Douze; Francisco Massa; Alexandre Sablayrolles; Herve Jegou',
        'year': 2021,
        'venue': 'Proceedings of the 38th International Conference on Machine Learning',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://proceedings.mlr.press/v139/touvron21a.html',
        'abstract_url': 'https://proceedings.mlr.press/v139/touvron21a.html',
        'method_url': 'https://proceedings.mlr.press/v139/touvron21a.html',
        'relevance_note': 'Data-efficient transformer training reference relevant to lightweight visual modeling trade-offs.',
        'entry_type': 'inproceedings',
        'booktitle': 'Proceedings of the 38th International Conference on Machine Learning',
        'url': 'https://proceedings.mlr.press/v139/touvron21a.html',
    },
    {
        'tier': 'tier3',
        'title': 'Deformable DETR: Deformable Transformers for End-to-End Object Detection',
        'ref_key': 'zhu2021deformabledetr',
        'authors': 'Xizhou Zhu; Weijie Su; Lewei Lu; Bin Li; Xiaogang Wang; Jifeng Dai',
        'year': 2021,
        'venue': 'International Conference on Learning Representations',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://openreview.net/forum?id=gZ9hCDWe6ke',
        'abstract_url': 'https://openreview.net/forum?id=gZ9hCDWe6ke',
        'method_url': 'https://openreview.net/forum?id=gZ9hCDWe6ke',
        'relevance_note': 'Efficient visual transformer detection paper relevant to image-feature attention trade-offs.',
        'entry_type': 'inproceedings',
        'booktitle': 'International Conference on Learning Representations',
        'url': 'https://openreview.net/forum?id=gZ9hCDWe6ke',
    },
    {
        'tier': 'tier3',
        'title': 'Stand-Alone Self-Attention in Vision Models',
        'ref_key': 'ramachandran2019standalone',
        'authors': 'Prajit Ramachandran; Niki Parmar; Ashish Vaswani; Irwan Bello; Anselm Levskaya; Jon Shlens',
        'year': 2019,
        'venue': 'Advances in Neural Information Processing Systems 32',
        'peer_reviewed': 'true',
        'doi_or_url': 'https://proceedings.neurips.cc/paper/2019/hash/3416a75f4cea9109507cacd8e2f2aefc-Abstract.html',
        'abstract_url': 'https://proceedings.neurips.cc/paper/2019/hash/3416a75f4cea9109507cacd8e2f2aefc-Abstract.html',
        'method_url': 'https://proceedings.neurips.cc/paper/2019/hash/3416a75f4cea9109507cacd8e2f2aefc-Abstract.html',
        'relevance_note': 'Vision self-attention paper relevant to standalone attention-based perception layers.',
        'entry_type': 'inproceedings',
        'booktitle': 'Advances in Neural Information Processing Systems 32',
        'url': 'https://proceedings.neurips.cc/paper/2019/hash/3416a75f4cea9109507cacd8e2f2aefc-Abstract.html',
    },
]


def make_entry_from_lookup(row: dict, tier: str, ref_key: str, relevance_note: str) -> dict:
    venue = clean_text(row['venue'])
    title = clean_text(row['matched_title'])
    authors = clean_text(row['authors'])
    doi_or_url = row['doi_or_url']
    entry_type = 'article' if row['type'] == 'journal-article' else 'inproceedings'
    result = {
        'tier': tier,
        'title': title,
        'ref_key': ref_key,
        'authors': authors,
        'year': row['year'],
        'venue': venue,
        'peer_reviewed': 'true',
        'doi_or_url': doi_or_url,
        'abstract_url': doi_or_url,
        'method_url': doi_or_url,
        'relevance_note': relevance_note,
        'entry_type': entry_type,
    }
    if doi_or_url.startswith('https://doi.org/'):
        result['doi'] = doi_or_url.replace('https://doi.org/', '')
    else:
        result['url'] = doi_or_url
    if entry_type == 'article':
        result['journal'] = venue
    else:
        result['booktitle'] = venue
    return result


def bib_escape(text: str) -> str:
    return text.replace('{', '\\{').replace('}', '\\}')


def build() -> list[dict]:
    lookup = load_lookup()
    entries: list[dict] = []
    for tier, requested_title, ref_key, note in GOOD_TITLES:
        row = lookup[requested_title]
        entries.append(make_entry_from_lookup(row, tier, ref_key, note))
    entries.extend(MANUAL_ENTRIES)
    tier_rank = {'tier1': 0, 'tier2': 1, 'tier3': 2}
    entries.sort(key=lambda e: tier_rank[e['tier']])
    return entries


def write_outputs(entries: list[dict]) -> None:
    fieldnames = [
        'ref_key', 'tier', 'title', 'authors', 'year', 'venue', 'peer_reviewed',
        'doi_or_url', 'abstract_url', 'method_url', 'relevance_note'
    ]
    with CSV_PATH.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            writer.writerow({field: entry[field] for field in fieldnames})

    lines: list[str] = []
    for entry in entries:
        lines.append(f"% relevance: {entry['relevance_note']}")
        lines.append(f"@{entry['entry_type']}{{{entry['ref_key']},")
        lines.append(f"  author = {{{bib_escape(entry['authors'])}}},")
        lines.append(f"  title = {{{bib_escape(entry['title'])}}},")
        if entry['entry_type'] == 'article':
            lines.append(f"  journal = {{{bib_escape(entry['journal'])}}},")
        else:
            lines.append(f"  booktitle = {{{bib_escape(entry['booktitle'])}}},")
        lines.append(f"  year = {{{entry['year']}}},")
        if 'doi' in entry:
            lines.append(f"  doi = {{{entry['doi']}}},")
        else:
            lines.append(f"  url = {{{entry['url']}}},")
        lines.append('}')
        lines.append('')
    BIB_PATH.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')


def main() -> int:
    entries = build()
    if len(entries) != 50:
        raise SystemExit(f'Expected 50 entries, got {len(entries)}')
    write_outputs(entries)
    print(f'Wrote {len(entries)} entries to {CSV_PATH} and {BIB_PATH}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
