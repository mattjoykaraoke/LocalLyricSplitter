import re
import unicodedata

WORD_JOINERS = {"'", "’", "‘", "/", "_", "-"}


def is_lyric_token_char(char):
    return (
        char.isalnum()
        or unicodedata.category(char).startswith("M")
        or char in WORD_JOINERS
    )


def split_lyric_tokens(content):
    if not content:
        return [""]

    parts = []
    current = []
    current_is_token = None

    for char in content:
        is_token = is_lyric_token_char(char)
        if current and is_token != current_is_token:
            parts.append("".join(current))
            current = []

        current.append(char)
        current_is_token = is_token

    if current:
        parts.append("".join(current))

    return parts

def sanitize_lyrics_text(content):
    """Removes Genius metadata, ads, and structural tags while preserving stanza spacing."""
    # Normalize curled apostrophes to straight ones to prevent dictionary matching issues
    content = content.replace("’", "'").replace("‘", "'")

    lines = content.splitlines()

    # Un-mash first line if it contains a bracket
    if lines and "[" in lines[0] and not lines[0].strip().startswith("["):
        idx = lines[0].find("[")
        mashed_text = lines[0][:idx]
        if any(word in mashed_text.lower() for word in ["contributor", "lyrics"]):
            lines.insert(1, lines[0][idx:])
            lines[0] = mashed_text

    # 1. Pre-pass: If we find an early bracket (e.g., [Verse 1]), wipe out the top block completely.
    first_bracket_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            first_bracket_idx = i
            break

    if first_bracket_idx > 0:
        header_text = "\n".join(lines[:first_bracket_idx]).lower()
        # Verify it's a metadata block before deleting (e.g. contributor counts, etc.)
        if any(word in header_text for word in ["contributor", "lyrics", "read more"]):
            lines = lines[first_bracket_idx:]

    # 2. Line-by-Line cleanup
    cleaned_lines = []
    skip_count = 0
    skipping_blurb = False

    for line in lines:
        stripped = line.strip()

        if stripped.lower() == "read more":
            continue

        # Catch stray "Song Title Lyrics" right at the top
        if len(cleaned_lines) == 0:
            # Handle mashed "5 ContributorsSong Name LyricsLyric Start"
            stripped = re.sub(r"^\d+\s*Contributors.*?Lyrics", "", stripped, flags=re.IGNORECASE).strip()
            if stripped == "":
                continue

        # Strip brackets and clean
        line_no_tags = re.sub(r"\[.*?\]", "", stripped).strip()

        # Prevent multiple stacked blank lines
        if line_no_tags == "":
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
        else:
            cleaned_lines.append(line_no_tags)

    return "\n".join(cleaned_lines).strip()

def auto_split_text(content, pyphen_dic, trip_ups):
    parts = split_lyric_tokens(content)
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
            for m in re.finditer(r"[\w/_']+", full_line)
            if m.start() <= col <= m.end()
        ),
        None,
    )
    if not target:
        return current_content, False

    base = re.sub(r"[/_]", "", target)
    if not base:
        return current_content, False

    # Regex to match the word with any combination of slashes/underscores
    pattern = re.compile(
        rf"(?<!\w){''.join([re.escape(c) + r'[/_]*' for c in base])[:-5]}(?!\w)",
        re.IGNORECASE,
    )

    # Find what this word was in the previous state
    pre_match = pattern.search(pre_keypress_snapshot)
    if pre_match:
        old_target = pre_match.group()
        # If the word changed but base letters are the same, and slashes are involved
        if old_target != target and (
            "/" in old_target or "_" in old_target or "/" in target or "_" in target
        ):
            new_text = pattern.sub(target, current_content)
            if new_text != current_content:
                return new_text, True

    return current_content, False
