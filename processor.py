import re

def sanitize_lyrics_text(content):
    """Removes Genius metadata, ads, and structural tags while preserving stanza spacing."""
    # Normalize curled apostrophes to straight ones to prevent dictionary matching issues
    content = content.replace("’", "'").replace("‘", "'")

    lines = content.splitlines()

    # 1. Pre-pass: If we find an early bracket (e.g., [Verse 1]), wipe out the top block completely.
    first_bracket_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            first_bracket_idx = i
            break

    if first_bracket_idx > 0:
        header_text = "\n".join(lines[:first_bracket_idx]).lower()
        # Verify it's a metadata block before deleting
        if (
            "contributor" in header_text
            or "lyrics" in header_text
            or "read more" in header_text
        ):
            lines = lines[first_bracket_idx:]

    # 2. Line-by-Line cleanup
    cleaned_lines = []
    skip_count = 0
    skipping_blurb = False

    for line in lines:
        stripped = line.strip()

        # Handle dynamic blurb skipping (e.g., descriptions before the lyrics)
        if skipping_blurb:
            if (
                stripped.lower() == "read more"
                or stripped.startswith("[")
                or stripped == ""
            ):
                skipping_blurb = False
                if stripped.lower() == "read more":
                    continue
            if skipping_blurb:
                continue

        if skip_count > 0:
            skip_count -= 1
            continue

        # Triggers to start skipping lines
        if re.match(r"^\d+\s*Contributors?$", stripped, re.IGNORECASE):
            skipping_blurb = True
            continue

        if re.match(r"^See .* Live$", stripped, re.IGNORECASE):
            skip_count = 8
            continue

        if "You might also like" in stripped:
            skip_count = 6
            continue

        if stripped.lower() == "read more":
            continue

        # Catch stray "Song Title Lyrics" right at the top
        if stripped.lower().endswith("lyrics") and len(cleaned_lines) == 0:
            continue

        # Strip brackets and clean
        line_no_tags = re.sub(r"\[.*?\]", "", line).strip()

        # Prevent multiple stacked blank lines
        if line_no_tags == "":
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line_no_tags)

    return "\n".join(cleaned_lines).strip()

def auto_split_text(content, pyphen_dic, trip_ups):
    parts = re.split(r"([^a-zA-Z0-9'/_-]+)", content)
    processed = []
    for p in parts:
        low = p.lower()
        if low in trip_ups:
            res = trip_ups[low]
            processed.append(res.capitalize() if p[0].isupper() else res)
        elif (
            not p.strip() or not any(c.isalnum() for c in p) or "/" in p or "_" in p
        ):
            processed.append(p)
        elif "-" in p:
            sub_words = p.split("-")
            hyphenated_chunks = []
            for sub in sub_words:
                sub_low = sub.lower()
                if sub_low in trip_ups:
                    res = trip_ups[sub_low]
                    hyphenated_chunks.append(
                        res.capitalize() if sub and sub[0].isupper() else res
                    )
                else:
                    hyphenated_chunks.append(pyphen_dic.inserted(sub, hyphen="/"))
            processed.append("-/".join(hyphenated_chunks))
        else:
            processed.append(pyphen_dic.inserted(p, hyphen="/"))

    return "".join(processed)

def calculate_live_sync(pre_keypress_snapshot, current_content, full_line, col):
    target = next(
        (
            m.group()
            for m in re.finditer(r"\S+", full_line)
            if m.start() <= col <= m.end()
        ),
        None,
    )
    if target and ("/" in target or "_" in target):
        base = re.sub(r"[/_]", "", target)
        pattern = re.compile(
            rf"(?<!\w){''.join([re.escape(c) + r'[/_]*' for c in base])[:-5]}(?!\w)",
            re.IGNORECASE,
        )
        if pattern.search(pre_keypress_snapshot):
            new_text = pattern.sub(target, current_content)
            return new_text, True
    return current_content, False
