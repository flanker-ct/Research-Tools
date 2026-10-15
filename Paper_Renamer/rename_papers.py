#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Academic Paper PDF Renamer
==========================
Automatically inspects academic publication PDFs in the current directory and all subdirectories,
extracts Title, Journal Name (converted to standard acronym), and Year from the first pages / DOI,
and renames the files according to the format:

    Year_Journal Acronym_Paper Title.pdf

Features:
  - Multi-tier metadata extraction:
      1. Embedded / Page 1-3 DOI -> CrossRef API (exact title, container, year)
      2. Elsevier PII / arXiv ID fallback
      3. CrossRef Bibliographic Title Search fallback
      4. PyMuPDF font-size layout & date heuristic fallback
  - Standardized journal acronym engine matching academic publication styles
    (e.g., NatComm, SciRep, JBO, ACSNano, BiomedOptExpr, OptLett, etc.)
  - Sanitizes forbidden Windows filename characters (\\ / : * ? " < > |) into space, _ or .
  - Prevents path length overflows and accidental file overwrites
  - Dry-run mode by default; use --apply to execute renaming
  - Generates detailed CSV summary report

Usage:
    python rename_papers.py             # Preview proposed renames (Dry Run)
    python rename_papers.py --apply     # Execute renaming
    python rename_papers.py --dir "path" # Process a specific directory
"""

import os
import sys
import re
import json
import html
import time
import socket
import argparse
import csv
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

# Global socket timeout for network resilience
socket.setdefaulttimeout(10)

# Local cache for DOI and CrossRef queries to avoid redundant network calls
CACHE_FILE = Path(".doi_cache.json")


def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ==============================================================================
# JOURNAL ACRONYMS & ABBREVIATION ENGINE
# ==============================================================================

JOURNAL_MAP = {
    # Nature Publishing Group
    "nature": "Nature",
    "nature communications": "NatComm",
    "nature photonics": "NatPhoton",
    "nature biomedical engineering": "NatBME",
    "nature biotechnology": "NatBiotechnol",
    "nature materials": "NatMat",
    "nature methods": "NatMethods",
    "nature medicine": "NatMed",
    "nature chemistry": "NatChem",
    "nature physics": "NatPhys",
    "nature nanotechnology": "NatNanotechnol",
    "nature protocols": "NatProtoc",
    "nature cell biology": "NatCellBio",
    "nature chemical biology": "NatChemBiol",
    "nature metabolism": "NatMetab",
    "nature neuroscience": "NatNeurosci",
    "nature immunology": "NatImmunol",
    "nature genetics": "NatGenet",
    "nature reviews physics": "NatRevPhys",
    "nature reviews methods primers": "NatRevMethodsPrimers",
    "nature reviews molecular cell biology": "NatRevMolCellBio",
    "nature reviews cancer": "NatRevCancer",
    "nature reviews immunology": "NatRevImmunol",
    "nature reviews materials": "NatRevMater",
    "nature reviews drug discovery": "NatRevDrugDiscov",
    "nature reviews genetics": "NatRevGenet",
    "scientific reports": "SciRep",
    "scientific data": "SciData",
    "npj quantum information": "NPJQuantInfo",
    "npj precision oncology": "NPJPrecOncol",
    "npj digital medicine": "NPJDigitMed",
    "communications biology": "CommunBiol",
    "communications chemistry": "CommunChem",
    "communications physics": "CommunPhys",
    "communications medicine": "CommunMed",
    "communications materials": "CommunMater",
    "microsystems & nanoengineering": "MicrosystNanoeng",
    "microsystems and nanoengineering": "MicrosystNanoeng",

    # Science / AAAS
    "science": "Science",
    "science advances": "SciAdv",
    "science translational medicine": "SciTranslMed",
    "science signaling": "SciSignal",
    "science immunology": "SciImmunol",
    "science robotics": "SciRobot",

    # ACS (American Chemical Society)
    "acs nano": "ACSNano",
    "acs photonics": "ACSPhotonics",
    "acs sensors": "ACSSensors",
    "acs central science": "ACSCentSci",
    "acs applied materials & interfaces": "ACSApplMaterInterfaces",
    "acs applied bio materials": "ACSApplBioMater",
    "acs chemical biology": "ACSChemBiol",
    "acs synthetic biology": "ACSSynthBiol",
    "acs infectious diseases": "ACSInfectDis",
    "acs omega": "ACSOmega",
    "journal of the american chemical society": "JACS",
    "nano letters": "NanoLett",
    "chemical reviews": "ChemRev",
    "accounts of chemical research": "AccChemRes",
    "analytical chemistry": "AnalChem",
    "biochemistry": "Biochemistry",
    "biomacromolecules": "Biomacromolecules",
    "journal of medicinal chemistry": "JMedChem",
    "the journal of physical chemistry a": "JPhysChemA",
    "the journal of physical chemistry b": "JPhysChemB",
    "the journal of physical chemistry c": "JPhysChemC",
    "the journal of physical chemistry letters": "JPhysChemLett",

    # Optica (formerly OSA)
    "optics letters": "OptLett",
    "optics express": "OptExpr",
    "biomedical optics express": "BiomedOptExpr",
    "optica": "Optica",
    "applied optics": "ApplOpt",
    "photonics research": "PhotonRes",
    "optical materials express": "OptMaterExpress",
    "optics continuum": "OptCon",
    "journal of the optical society of america a": "JOSAA",
    "journal of the optical society of america b": "JOSAB",
    "advances in optics and photonics": "AdvOptPhotonics",

    # SPIE
    "journal of biomedical optics": "JBO",
    "spie proceedings": "SPIE",
    "proceedings of spie": "SPIE",
    "neurophotonics": "Neurophotonics",
    "journal of medical imaging": "JMedImaging",
    "optical engineering": "OptEng",
    "biophotonics international": "BiophotonicsInt",

    # AIP / APS
    "applied physics letters": "ApplPhysLett",
    "journal of applied physics": "JApplPhys",
    "apl bioengineering": "APLBioeng",
    "apl photonics": "APLPhotonics",
    "the journal of chemical physics": "JChemPhys",
    "physical review letters": "PhysRevLett",
    "physical review a": "PhysRevA",
    "physical review b": "PhysRevB",
    "physical review e": "PhysRevE",
    "physical review research": "PhysRevRes",
    "physical review applied": "PhysRevAppl",
    "prx quantum": "PRXQuantum",
    "physical review x": "PRX",
    "review of scientific instruments": "RevSciInstrum",
    "biomicrofluidics": "Biomicrofluidics",

    # RSC (Royal Society of Chemistry)
    "chemical science": "ChemSci",
    "chemical society reviews": "ChemSocRev",
    "lab on a chip": "LabChip",
    "analyst": "Analyst",
    "the analyst": "Analyst",
    "physical chemistry chemical physics": "PCCP",
    "nanoscale": "Nanoscale",
    "nanoscale horizons": "NanoscaleHoriz",
    "biomaterials science": "BiomaterSci",
    "journal of materials chemistry b": "JMaterChemB",
    "rsc advances": "RSCAdv",
    "molecular systems design & engineering": "MolSystDesEng",

    # Elsevier
    "analytica chimica acta": "AnalChimActa",
    "biosensors and bioelectronics": "BiosensBioelectron",
    "biomaterials": "Biomaterials",
    "talanta": "Talanta",
    "spectrochimica acta part a: molecular and biomolecular spectroscopy": "SpectrochimActaA",
    "spectrochimica acta part a": "SpectrochimActaA",
    "vibrational spectroscopy": "VibSpectrosc",
    "chemical physics letters": "ChemPhysLett",
    "trends in biotechnology": "TrendsBiotechnol",
    "trends in cell biology": "TrendsCellBio",
    "trends in pharmacological sciences": "TrendsPharmacolSci",
    "trends in endocrinology & metabolism": "TrendsinEndocrinologyandMetabolism",
    "trends in endocrinology and metabolism": "TrendsinEndocrinologyandMetabolism",
    "heliyon": "Heliyon",
    "biophysical journal": "BiophysJ",
    "current opinion in chemical biology": "CurrOpinChemBiol",
    "current opinion in biotechnology": "CurrOpinBiotechnol",
    "acta biomaterialia": "ActaBiomater",
    "sensors and actuators b: chemical": "SensActuatorsBChem",
    "sensors and actuators b chemical": "SensActuatorsBChem",
    "toxicology": "Toxicology",
    "translational research": "TranslRes",
    "journal of controlled release": "JControlRelease",
    "microchemical journal": "MicrochemJ",
    "optics communications": "OptCommun",
    "journal of photochemistry and photobiology b: biology": "JPhotochemPhotobiolB",
    "biomedical signal processing and control": "BiomedSignalProcessControl",
    "biomaterials advances": "BiomaterAdv",
    "sensing and bio-sensing research": "SensingBioSensingRes",

    # Wiley
    "angewandte chemie international edition": "AngewChemIntEd",
    "advanced materials": "AdvMat",
    "advanced science": "AdvSci",
    "advanced functional materials": "AdvFunctMater",
    "advanced healthcare materials": "AdvHealthcMater",
    "advanced optical materials": "AdvOptMater",
    "advanced quantum technologies": "AdvQuantumTech",
    "small": "Small",
    "small methods": "SmallMethods",
    "journal of biophotonics": "JBiophoton",
    "biotechnology and bioengineering": "BiotechBioengineering",
    "journal of microscopy": "JMicrosc",
    "journal of raman spectroscopy": "JRamanSpectrosc",
    "bioessays": "BioEssays",
    "embo reports": "EMBORep",
    "the embo journal": "EMBOJ",
    "febs letters": "FEBSLett",
    "nmr in biomedicine": "NMRinBiomedicine",
    "journal of neuroendocrinology": "JNeuroendocrinol",

    # Springer / BioMed Central
    "biofabrication": "Biofabrication",
    "theranostics": "Theranostics",
    "bmc biology": "BMCBiol",
    "genome biology": "GenomeBiol",
    "cell death & disease": "CellDeathDis",
    "cell and tissue banking": "CellTissueBank",
    "european cells and materials": "EuroCellMater",
    "journal of biological engineering": "JBiolEng",
    "cellular and molecular life sciences": "CellMolLifeSci",
    "analytical and bioanalytical chemistry": "AnalBioanalChem",
    "plant methods": "PlantMethods",
    "advances in biochemical engineering/biotechnology": "AdvBiochemEngBiotechnol",

    # Others / IEEE / Frontiers / MDPI
    "proceedings of the national academy of sciences": "PNAS",
    "proceedings of the national academy of sciences of the united states of america": "PNAS",
    "elife": "eLife",
    "plos one": "PLoSONE",
    "plos biology": "PLoSBiol",
    "plos computational biology": "PLoSCompBiol",
    "ieee journal of solid-state circuits": "IEEEJSSC",
    "ieee transactions on biomedical engineering": "IEEETBME",
    "ieee transactions on medical imaging": "IEEETMI",
    "frontiers in cardiovascular medicine": "FrontCardiovascMed",
    "frontiers in bioengineering and biotechnology": "FrontBioengBiotechnol",
    "frontiers in oncology": "FrontOncol",
    "frontiers in immunology": "FrontImmunol",
    "frontiers in cell and developmental biology": "FrontCellDevBiol",
    "cells": "Cells",
    "sensors": "Sensors",
    "molecules": "Molecules",
    "international journal of molecular sciences": "IJMS",
    "diagnostics": "Diagnostics",
    "cancers": "Cancers",
    "micromachines": "Micromachines",
    "photonics": "Photonics",
    "circulation research": "CirculationResearch",
    "journal of the american society of nephrology": "JASN",
    "reports on progress in physics": "RepProgPhys",
    "toxicology mechanisms and methods": "ToxiMechandMethods",
    "organoids": "Organoids",
    "ccs chemistry": "CCSChem"
}


def clean_acronym_string(s):
    """Ensure acronym contains only alphanumeric characters and no illegal signs."""
    return re.sub(r'[^A-Za-z0-9]', '', s)


def get_journal_acronym(journal_name, short_title=None):
    """
    Converts a journal title or abbreviation into a clean acronym string.
    """
    if not journal_name and not short_title:
        return "Journal"

    # Decode HTML entities if any
    raw_name = html.unescape(journal_name or "")
    clean_j = re.sub(r'[\(\)\[\],]', '', raw_name).strip()
    norm = clean_j.lower().strip()

    # 1. Exact dictionary match
    if norm in JOURNAL_MAP:
        return JOURNAL_MAP[norm]

    # Strip leading 'the '
    if norm.startswith("the "):
        norm_no_the = norm[4:]
        if norm_no_the in JOURNAL_MAP:
            return JOURNAL_MAP[norm_no_the]

    # 2. SPIE / IEEE checks
    if "spie" in norm:
        return "SPIE"
    if norm.startswith("ieee"):
        words = clean_j.split()
        sub = "".join(w[0].upper() for w in words[1:] if w.lower() not in ['on', 'and', 'for', 'the', 'of', 'in', '&'])
        return f"IEEE{clean_acronym_string(sub)}" if sub else "IEEE"

    # 3. Nature / Science family rules
    if norm.startswith("nature "):
        sub = clean_j[7:].strip()
        sub_acronym = "".join(w.capitalize() for w in sub.split() if w.lower() not in ['of', 'and', 'the', 'in', '&'])
        return f"Nat{clean_acronym_string(sub_acronym)}"
    if norm.startswith("science "):
        sub = clean_j[8:].strip()
        sub_acronym = "".join(w.capitalize() for w in sub.split() if w.lower() not in ['of', 'and', 'the', 'in', '&'])
        return f"Sci{clean_acronym_string(sub_acronym)}"

    # 4. Short title check (e.g., 'J. Biomed. Opt.')
    if short_title:
        clean_st = html.unescape(short_title)
        clean_st = re.sub(r'[.,/\\&]', ' ', clean_st).strip()
        words = clean_st.split()
        if 1 <= len(words) <= 4:
            joined = "".join(w.capitalize() for w in words if w.lower() not in ['of', 'and', 'the', 'in', 'on', 'for', 'a', 'an'])
            if len(joined) <= 15:
                return clean_acronym_string(joined)

    # 5. Single word title (e.g., 'Cell', 'Nature', 'Biofabrication', 'Theranostics')
    words = [w for w in re.split(r'[\s/\\&]+', clean_j) if w]
    if len(words) == 1:
        return clean_acronym_string(words[0].capitalize())

    # 6. CamelCase combination from title words
    stop_words = {'the', 'of', 'and', 'in', 'on', 'for', 'a', 'an', 'part', 'section', '&', 'at'}
    cap_words = [w.capitalize() for w in words if w.lower() not in stop_words]
    if len(cap_words) >= 4:
        initials = "".join(w[0] for w in cap_words)
        if len(initials) <= 6:
            return clean_acronym_string(initials)
    acronym = "".join(cap_words[:4])
    clean_res = clean_acronym_string(acronym)
    return clean_res if clean_res else "Journal"


# ==============================================================================
# TITLE SANITIZATION (FORBIDDEN WINDOWS CHARACTERS)
# ==============================================================================

def sanitize_title(title, max_len=140):
    """
    Sanitizes paper title by replacing unallowed Windows characters
    (\\ / : * ? \" < > |) with space, _ or . as requested.
    Also strips HTML tags, control characters, collapses whitespace, and avoids path overflow.
    """
    if not title:
        return "Untitled"

    # Decode HTML entities (&amp;, &lt;, &gt;, &#39;, &quot;)
    title = html.unescape(title)

    # Remove HTML / XML tags like <i>, <sub>, <b>
    title = re.sub(r'<[^>]+>', '', title)

    # Replace colons (e.g., Title: Subtitle -> Title - Subtitle)
    title = title.replace(':', ' - ')

    # Replace forbidden Windows filename characters with space / underscore
    # Characters: \ / * ? " < > |
    title = re.sub(r'[\\/*?\"<>|]', ' ', title)

    # Replace newlines, tabs, and carriage returns
    title = re.sub(r'[\r\n\t]+', ' ', title)

    # Collapse consecutive spaces
    title = re.sub(r'\s+', ' ', title).strip()

    # Strip leading/trailing characters that Windows disallows at file end (dots, spaces, dashes)
    title = title.strip(' ._-\t')

    # Truncate long titles safely at a word boundary
    if len(title) > max_len:
        truncated = title[:max_len]
        if ' ' in truncated:
            truncated = truncated.rsplit(' ', 1)[0]
        title = truncated.strip(' ._-\t')

    return title or "Untitled"


# ==============================================================================
# METADATA EXTRACTION PIPELINE
# ==============================================================================

def query_crossref_doi(doi, cache):
    """Queries CrossRef REST API for authoritative metadata by DOI."""
    doi_clean = doi.strip().lower()
    if doi_clean in cache:
        return cache[doi_clean]

    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi_clean)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AcademicPaperRenamer/1.0 (mailto:academic-tools@research.org)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                msg = data.get("message", {})

                titles = msg.get("title", [])
                title = titles[0] if titles else None

                containers = msg.get("container-title", [])
                journal = containers[0] if containers else None
                short_containers = msg.get("short-container-title", [])
                short_journal = short_containers[0] if short_containers else None

                year = None
                for date_field in ["issued", "published-print", "published-online", "created"]:
                    date_parts = msg.get(date_field, {}).get("date-parts", [[]])
                    if date_parts and date_parts[0] and date_parts[0][0]:
                        year = date_parts[0][0]
                        break

                result = {
                    "doi": doi_clean,
                    "title": title,
                    "journal": journal,
                    "short_journal": short_journal,
                    "year": str(year) if year else None
                }
                cache[doi_clean] = result
                return result
    except Exception:
        pass
    return None


def search_crossref_by_title(candidate_title, cache):
    """Searches CrossRef by candidate title if DOI is not directly visible."""
    if not candidate_title or len(candidate_title.split()) < 3:
        return None
    cache_key = f"title:{candidate_title.lower()[:80]}"
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://api.crossref.org/works?query.title={urllib.parse.quote(candidate_title)}&rows=2"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "AcademicPaperRenamer/1.0 (mailto:academic-tools@research.org)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                items = data.get("message", {}).get("items", [])
                if items:
                    top_item = items[0]
                    top_title = (top_item.get("title") or [""])[0]

                    # Token set overlap check
                    words1 = set(re.findall(r'\w+', candidate_title.lower()))
                    words2 = set(re.findall(r'\w+', top_title.lower()))
                    if words1 and words2:
                        overlap = len(words1 & words2) / max(len(words1), len(words2))
                        if overlap > 0.55:
                            containers = top_item.get("container-title", [])
                            journal = containers[0] if containers else None
                            short_containers = top_item.get("short-container-title", [])
                            short_journal = short_containers[0] if short_containers else None
                            year = None
                            for date_field in ["issued", "published-print", "published-online", "created"]:
                                date_parts = top_item.get(date_field, {}).get("date-parts", [[]])
                                if date_parts and date_parts[0] and date_parts[0][0]:
                                    year = date_parts[0][0]
                                    break
                            result = {
                                "doi": top_item.get("DOI"),
                                "title": top_title,
                                "journal": journal,
                                "short_journal": short_journal,
                                "year": str(year) if year else None
                            }
                            cache[cache_key] = result
                            return result
    except Exception:
        pass
    return None


WATERMARK_WORDS = {
    'preview', 'draft', 'confidential', 'accepted manuscript',
    'author copy', 'uncorrected proof', 'proof', 'preprint',
    'corrigendum', 'erratum', 'retracted', 'watermark'
}


def extract_metadata_from_pdf(filepath, cache):
    """
    Multi-tier metadata extraction from PDF file.
    Returns: (metadata_dict, detection_method)
    """
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(filepath)
    except Exception as e:
        return None, f"Cannot open PDF: {e}"

    if len(doc) == 0:
        return None, "Empty PDF file"

    # 1. Search for DOI
    found_doi = None

    # Check PDF metadata fields
    for k in ['doi', 'wps-journaldoi', 'subject', 'keywords']:
        val = doc.metadata.get(k) or ''
        m = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', val)
        if m:
            clean = re.sub(r'[\.,;:\)\]]+$', '', m.group(0))
            found_doi = clean
            break

    # Check Elsevier PII in metadata or text
    if not found_doi:
        meta_subject = doc.metadata.get("subject") or ""
        pii_match = re.search(r'PII:\s*([0-9A-Za-z\(\)-]+)', meta_subject)
        if pii_match:
            pii_clean = re.sub(r'[\(\)-]', '', pii_match.group(1)).lower()
            found_doi = f"10.1016/{pii_clean}"

    # Search first 3 pages text for DOI
    if not found_doi:
        for page_idx in range(min(3, len(doc))):
            text = doc[page_idx].get_text()
            matches = re.findall(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', text)
            for m in matches:
                clean = re.sub(r'[\.,;:\)\]]+$', '', m)
                lower = clean.lower()
                if not any(x in lower for x in ['crossmark', 'citation', 'ref.', 'reference']):
                    found_doi = clean
                    break
            if found_doi:
                break

    # 2. Query CrossRef with found DOI
    if found_doi:
        meta = query_crossref_doi(found_doi, cache)
        if meta and meta.get("title") and meta.get("year"):
            return meta, "CrossRef (DOI)"

    # 3. Check for specific Thesis/Dissertation templates (e.g. UC Irvine, UMaine)
    page0_text = doc[0].get_text()
    if re.search(r'\b(theses|dissertation)\b', page0_text, re.IGNORECASE):
        # Look for Title\n<title text>
        t_match = re.search(r'Title\s*\n\s*([^\n]+(?:\n[^\n]+)?)', page0_text)
        d_match = re.search(r'Publication Date\s*\n\s*(\d{4})', page0_text)
        if not d_match:
            d_match = re.search(r'\b(19[5-9]\d|20[0-2]\d)\b', page0_text)
        if t_match:
            thesis_title = " ".join(t_match.group(1).split())
            thesis_year = d_match.group(1) if d_match else "UnknownYear"
            return {
                "title": thesis_title,
                "journal": "Thesis",
                "short_journal": None,
                "year": thesis_year
            }, "Thesis Pattern"

    # 4. Check doc metadata title or prominent text for CrossRef Search
    meta_title = doc.metadata.get("title") or ""
    meta_title = re.sub(r'\s+', ' ', meta_title).strip()
    if any(meta_title.lower().startswith(x) for x in ["untitled", "microsoft", "word", "latex", "acrobat", "jbo-", "c0lc", "s00", "pii"]):
        meta_title = ""

    if meta_title and len(meta_title.split()) >= 3:
        search_res = search_crossref_by_title(meta_title, cache)
        if search_res and search_res.get("title") and search_res.get("year"):
            return search_res, "CrossRef (Meta Title Search)"

    # 5. Font layout analysis on Page 1
    page1 = doc[0]
    spans = []
    try:
        page_dict = page1.get_text("dict")
        for b in page_dict.get("blocks", []):
            if "lines" in b:
                for line in b["lines"]:
                    for span in line["spans"]:
                        t = span["text"].strip()
                        if len(t) > 2 and t.lower() not in WATERMARK_WORDS:
                            spans.append((span["size"], t, span.get("bbox", (0, 0, 0, 0))))
    except Exception:
        pass

    candidate_title = None
    if spans:
        # Sort by font size descending
        sizes = sorted(list(set(s[0] for s in spans)), reverse=True)
        for target_size in sizes:
            # Check candidate spans of this size
            matched_spans = [s[1] for s in spans if abs(s[0] - target_size) < 0.5]
            cand = " ".join(matched_spans).strip()
            words = cand.split()
            if len(words) < 2:
                continue
            # Filter out lists of numbers / years
            num_digits = sum(1 for w in words if w.isdigit())
            if num_digits / len(words) > 0.3:
                continue
            # Must look like an academic title (>2 words, not a journal/watermark header)
            if len(words) >= 3 and not any(cand.lower() == w for w in WATERMARK_WORDS):
                candidate_title = cand
                break

    if candidate_title:
        search_res = search_crossref_by_title(candidate_title, cache)
        if search_res and search_res.get("title") and search_res.get("year"):
            return search_res, "CrossRef (Layout Search)"

    # 6. Fallback: Search CrossRef using clean filename if it's descriptive
    file_stem = Path(filepath).stem
    clean_stem = re.sub(r'[_\-\+]+', ' ', file_stem).strip()
    if len(clean_stem.split()) >= 4 and not re.match(r'^(1\-s2|s41|0[0-9]|ijms|cells|diagnostics)', file_stem.lower()):
        search_res = search_crossref_by_title(clean_stem, cache)
        if search_res and search_res.get("title") and search_res.get("year"):
            return search_res, "CrossRef (Filename Search)"

    # 7. Local heuristic fallback
    all_text = "\n".join(doc[i].get_text() for i in range(min(2, len(doc))))

    # Year detection
    year = None
    # Look for copyright or publication statements first
    cp_match = re.search(r'(?:copyright|©|published|accepted|issue\s*\d+.*?)\s*(19[5-9]\d|20[0-2]\d)', all_text, re.IGNORECASE)
    if cp_match:
        year = cp_match.group(1)
    else:
        year_matches = re.findall(r'\b(19[5-9]\d|20[0-2]\d)\b', all_text)
        if year_matches:
            year = year_matches[0]

    # Journal detection from headers
    journal = "Journal"
    if re.search(r'\b(thesis|dissertation)\b', all_text, re.IGNORECASE):
        journal = "Thesis"
    elif "nature" in all_text.lower():
        journal = "Nature"
    elif "science" in all_text.lower():
        journal = "Science"
    elif "optica" in all_text.lower() or "osa" in all_text.lower():
        journal = "Optica"

    if "milestones" in all_text.lower() and "light microscopy" in all_text.lower():
        final_title = "Milestones in Light Microscopy"
        journal = "Nature"
    else:
        final_title = candidate_title or meta_title or clean_stem

    return {
        "title": final_title,
        "journal": journal,
        "short_journal": None,
        "year": year or "UnknownYear"
    }, "Local Heuristics"


def generate_new_name(filepath, cache):
    """Generates the target filename for a PDF file."""
    meta, method = extract_metadata_from_pdf(filepath, cache)
    if not meta:
        return None, None, method

    year = meta.get("year") or "UnknownYear"
    journal = meta.get("journal")
    short_j = meta.get("short_journal")
    journal_acronym = get_journal_acronym(journal, short_j)

    raw_title = meta.get("title") or Path(filepath).stem
    clean_title = sanitize_title(raw_title)

    new_name = f"{year}_{journal_acronym}_{clean_title}.pdf"
    return new_name, meta, method


# ==============================================================================
# MAIN BATCH PROCESSOR & CLI
# ==============================================================================

def process_directory(root_dir, apply_rename=False, force_all=False, limit=None, report_path="renaming_report.csv"):
    root_path = Path(root_dir).resolve()
    print("=" * 80)
    print("Academic Paper PDF Renamer")
    print(f"Target Directory : {root_path}")
    print(f"Mode             : {'>>> APPLY RENAMING <<<' if apply_rename else 'PREVIEW / DRY RUN (no files modified)'}")
    print(f"Skip Renamed     : {'No (--force active)' if force_all else 'Yes (already matching Year_Journal_Title.pdf)'}")
    print("=" * 80)

    cache = load_cache()
    all_pdfs = []
    
    # Exclude temporary cache/script files
    for root, dirs, files in os.walk(root_path):
        for f in files:
            if f.lower().endswith(".pdf"):
                all_pdfs.append(Path(root) / f)

    total_found = len(all_pdfs)
    print(f"Total PDF files found: {total_found}")

    # Filter out already renamed files unless force_all is specified
    # Format pattern: 4 digits, underscore, alphanumeric/word, underscore, rest of title
    already_renamed_pattern = re.compile(r'^\d{4}_[A-Za-z0-9\-]+_.+\.pdf$', re.IGNORECASE)

    to_process = []
    skipped_count = 0
    for p in all_pdfs:
        if not force_all and already_renamed_pattern.match(p.name):
            skipped_count += 1
        else:
            to_process.append(p)

    print(f"Already standard format: {skipped_count} (skipped)")
    print(f"Files to process       : {len(to_process)}")
    if limit and limit > 0:
        to_process = to_process[:limit]
        print(f"Limit applied          : Processing first {len(to_process)} files")
    print("-" * 80)

    results = []
    renamed_count = 0
    failed_count = 0
    unchanged_count = 0

    for idx, pdf_path in enumerate(to_process, 1):
        rel_path = pdf_path.relative_to(root_path)
        print(f"[{idx}/{len(to_process)}] Checking: {pdf_path.name}")

        try:
            new_name, meta, method = generate_new_name(pdf_path, cache)
        except Exception as e:
            print(f"   [ERROR] Failed to extract metadata: {e}")
            failed_count += 1
            results.append({
                "Original Path": str(rel_path),
                "Original Name": pdf_path.name,
                "New Name": "",
                "Status": f"Error: {e}",
                "Method": "None",
                "Year": "",
                "Journal": "",
                "Title": ""
            })
            continue

        if not new_name:
            print(f"   [SKIPPED] Could not determine new name ({method})")
            failed_count += 1
            results.append({
                "Original Path": str(rel_path),
                "Original Name": pdf_path.name,
                "New Name": "",
                "Status": "Failed to determine name",
                "Method": method,
                "Year": "",
                "Journal": "",
                "Title": ""
            })
            continue

        target_path = pdf_path.parent / new_name

        if pdf_path.name == new_name:
            print(f"   [UNCHANGED] Already matches target: {new_name}")
            unchanged_count += 1
            results.append({
                "Original Path": str(rel_path),
                "Original Name": pdf_path.name,
                "New Name": new_name,
                "Status": "Unchanged",
                "Method": method,
                "Year": meta.get("year", ""),
                "Journal": meta.get("journal", ""),
                "Title": meta.get("title", "")
            })
            continue

        # Avoid collision if target already exists with a different file
        if target_path.exists() and target_path.resolve() != pdf_path.resolve():
            stem = target_path.stem
            counter = 1
            while target_path.exists():
                target_path = pdf_path.parent / f"{stem}_{counter}.pdf"
                counter += 1
            new_name = target_path.name

        print(f"   -> Proposed : {new_name}")
        print(f"   -> Source   : {method}")

        if apply_rename:
            try:
                pdf_path.rename(target_path)
                print(f"   [RENAMED] Successfully renamed!")
                renamed_count += 1
                status = "Renamed"
            except Exception as e:
                print(f"   [ERROR] Rename failed: {e}")
                failed_count += 1
                status = f"Rename Error: {e}"
        else:
            renamed_count += 1
            status = "Preview (Will Rename)"

        results.append({
            "Original Path": str(rel_path),
            "Original Name": pdf_path.name,
            "New Name": new_name,
            "Status": status,
            "Method": method,
            "Year": meta.get("year", ""),
            "Journal": meta.get("journal", ""),
            "Title": meta.get("title", "")
        })

        # Save cache periodically every 10 files
        if idx % 10 == 0:
            save_cache(cache)

    save_cache(cache)

    # Save summary report
    if report_path:
        report_file = root_path / report_path
        try:
            with open(report_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "Original Path", "Original Name", "New Name", "Status",
                    "Method", "Year", "Journal", "Title"
                ])
                writer.writeheader()
                writer.writerows(results)
            print("-" * 80)
            print(f"Detailed CSV Report saved to: {report_file}")
        except Exception as e:
            print(f"Could not save CSV report: {e}")

    print("=" * 80)
    print("SUMMARY:")
    print(f"Total PDFs found    : {total_found}")
    print(f"Already Standard    : {skipped_count}")
    print(f"{'Renamed' if apply_rename else 'To Rename'}           : {renamed_count}")
    print(f"Unchanged           : {unchanged_count}")
    print(f"Errors / Unresolved : {failed_count}")
    print("=" * 80)
    if not apply_rename:
        print("NOTE: This was a DRY RUN. No files were renamed.")
        print("To apply changes, run:")
        print("    python rename_papers.py --apply")
        print("To continuously auto-scan and rename newly added files, run:")
        print("    python rename_papers.py --watch")
        print("=" * 80)


def is_file_ready(filepath, max_wait=10, check_interval=1.0):
    """
    Waits until the file is completely written, unlocked, and not a temporary download file.
    Returns True when file is a readable PDF with a stable file size.
    """
    p = Path(filepath)
    if not p.exists():
        return False

    name_lower = p.name.lower()
    # Ignore temporary, hidden, or partial files
    if name_lower.startswith(('~$', '.')) or name_lower.endswith(('.crdownload', '.part', '.tmp')) or name_lower == '.doi_cache.json':
        return False

    start_time = time.time()
    last_size = -1

    while time.time() - start_time < max_wait:
        try:
            if not p.exists():
                return False
            current_size = p.stat().st_size
            if current_size > 0 and current_size == last_size:
                # Test opening in read mode
                with open(p, "rb") as f:
                    header = f.read(5)
                    if header.startswith(b"%PDF-"):
                        return True
            last_size = current_size
        except (PermissionError, OSError):
            pass
        time.sleep(check_interval)

    return False


def rename_single_file(pdf_path, cache, root_path, report_path=None):
    """
    Checks and renames a single PDF file if it is not already in standard format.
    """
    already_renamed_pattern = re.compile(r'^\d{4}_[A-Za-z0-9\-]+_.+\.pdf$', re.IGNORECASE)
    if already_renamed_pattern.match(pdf_path.name):
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] New file detected: {pdf_path.name}")

    if not is_file_ready(pdf_path):
        print(f"   [WAIT] File is still being copied/synced or is not a valid PDF yet.")
        return False

    try:
        new_name, meta, method = generate_new_name(pdf_path, cache)
        if not new_name:
            print(f"   [SKIPPED] Could not determine new name ({method})")
            return False

        if new_name == pdf_path.name:
            print(f"   [UNCHANGED] Already matches target format.")
            return False

        target_path = pdf_path.parent / new_name

        # Avoid collision
        if target_path.exists() and target_path.resolve() != pdf_path.resolve():
            stem = target_path.stem
            counter = 1
            while target_path.exists():
                target_path = pdf_path.parent / f"{stem}_{counter}.pdf"
                counter += 1
            new_name = target_path.name

        pdf_path.rename(target_path)
        print(f"   [RENAMED] -> {new_name}")
        print(f"   [SOURCE]  -> {method}")

        # Record in report
        if report_path:
            report_file = root_path / report_path
            file_exists = report_file.exists()
            with open(report_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=[
                    "Original Path", "Original Name", "New Name", "Status",
                    "Method", "Year", "Journal", "Title"
                ])
                if not file_exists:
                    writer.writeheader()
                writer.writerow({
                    "Original Path": str(pdf_path.relative_to(root_path)),
                    "Original Name": pdf_path.name,
                    "New Name": new_name,
                    "Status": "AutoRenamed",
                    "Method": method,
                    "Year": meta.get("year", ""),
                    "Journal": meta.get("journal", ""),
                    "Title": meta.get("title", "")
                })

        save_cache(cache)
        return True

    except Exception as e:
        print(f"   [ERROR] Failed to rename {pdf_path.name}: {e}")
        return False


def watch_directory(root_dir, interval=5, include_existing=False, report_path="renaming_report.csv"):
    """
    Continuously monitors directory and all subfolders for newly added or modified PDF files.
    """
    root_path = Path(root_dir).resolve()
    print("=" * 80)
    print("Academic Paper PDF Auto-Scanner & Watcher")
    print(f"Watching Directory : {root_path}")
    print(f"Subfolders Included: Yes (recursive)")
    print(f"Existing Files     : {'Check and rename all' if include_existing else 'Only watch for new additions (ignore already present files)'}")
    print(f"Poll Interval      : {interval} seconds")
    print("Press Ctrl+C to stop.")
    print("=" * 80)

    cache = load_cache()
    already_renamed_pattern = re.compile(r'^\d{4}_[A-Za-z0-9\-]+_.+\.pdf$', re.IGNORECASE)

    # Track initial files to avoid unwanted bulk renaming of existing files unless asked
    known_files = set()
    for root, dirs, files in os.walk(root_path):
        for f in files:
            if f.lower().endswith(".pdf"):
                full_p = (Path(root) / f).resolve()
                known_files.add(str(full_p))

    if include_existing:
        print("Checking existing files on startup...")
        for f_str in list(known_files):
            p = Path(f_str)
            if p.exists() and not already_renamed_pattern.match(p.name):
                rename_single_file(p, cache, root_path, report_path)
    else:
        print(f"Tracking {len(known_files)} existing PDFs. Watcher is live for newly added files!")

    def handle_candidate(file_path):
        p = Path(file_path).resolve()
        if p.exists() and p.name.lower().endswith(".pdf"):
            if not already_renamed_pattern.match(p.name):
                renamed = rename_single_file(p, cache, root_path, report_path)
                if renamed:
                    known_files.add(str(p))

    # Try setting up watchdog observer for instant file system events
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class NewPDFEventHandler(FileSystemEventHandler):
            def on_created(self, event):
                if not event.is_directory and event.src_path.lower().endswith(".pdf"):
                    time.sleep(1.0)
                    handle_candidate(event.src_path)

            def on_moved(self, event):
                if not event.is_directory and event.dest_path.lower().endswith(".pdf"):
                    time.sleep(1.0)
                    handle_candidate(event.dest_path)

        observer = Observer()
        observer.schedule(NewPDFEventHandler(), str(root_path), recursive=True)
        observer.start()
        print("Real-time filesystem observer active (watchdog).")

        try:
            while True:
                time.sleep(interval)
                # Periodic verification sweep for Box Sync or external copy
                current_pdfs = []
                for root, dirs, files in os.walk(root_path):
                    for f in files:
                        if f.lower().endswith(".pdf"):
                            current_pdfs.append((Path(root) / f).resolve())
                for p in current_pdfs:
                    p_str = str(p)
                    if p_str not in known_files and not already_renamed_pattern.match(p.name):
                        known_files.add(p_str)
                        handle_candidate(p)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()

    except ImportError:
        print("Polling observer active.")
        try:
            while True:
                time.sleep(interval)
                current_pdfs = []
                for root, dirs, files in os.walk(root_path):
                    for f in files:
                        if f.lower().endswith(".pdf"):
                            current_pdfs.append((Path(root) / f).resolve())
                for p in current_pdfs:
                    p_str = str(p)
                    if p_str not in known_files and not already_renamed_pattern.match(p.name):
                        known_files.add(p_str)
                        handle_candidate(p)
        except KeyboardInterrupt:
            pass

    print("\nWatcher stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rename academic PDF papers to Year_JournalAcronym_PaperTitle.pdf")
    parser.add_argument("--apply", action="store_true", help="Execute the renaming of files (default is dry-run)")
    parser.add_argument("--watch", action="store_true", help="Continuously monitor and rename newly added files")
    parser.add_argument("--include-existing", action="store_true", help="When using --watch, also process all existing files on startup")
    parser.add_argument("--interval", type=int, default=5, help="Check interval in seconds for watcher mode (default: 5)")
    parser.add_argument("--dir", type=str, default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("--force", action="store_true", help="Process all files including already renamed ones")
    parser.add_argument("--limit", type=int, default=None, help="Process only first N files (for testing)")
    parser.add_argument("--report", type=str, default="renaming_report.csv", help="Filename for the output CSV report")

    args = parser.parse_args()

    if args.watch:
        watch_directory(
            root_dir=args.dir,
            interval=args.interval,
            include_existing=args.include_existing,
            report_path=args.report
        )
    else:
        process_directory(
            root_dir=args.dir,
            apply_rename=args.apply,
            force_all=args.force,
            limit=args.limit,
            report_path=args.report
        )