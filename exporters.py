import re
from pathlib import Path

def generate_kbp_content(title, artist, audio_path, lyrics):
    """Generates the Karaoke Builder Studio Unsynchronized File structure"""
    # Ensure audio path uses Windows-style backslashes
    if audio_path:
        audio_path = str(audio_path).replace("/", "\\")
        
    return f"""-----------------------------
KARAOKE BUILDER STUDIO
www.KaraokeBuilder.com

-----------------------------
HEADERV2

'--- Template Information ---

'Palette Colours (0-15)
  055,FFF,000,E70,940,CFF,033,0DD,077,FCF,303,F3F,818,000,FFF,000

'Styles (00-19)
'  Number,Name
'  Colour: Text,Outline,Text Wipe,Outline Wipe
'  Font  : Name,Size,Style,Charset
'  Other : Outline*4,Shadow*2,Wiping,Uppercase

  Style00,Default,1,2,3,4
    Arial,12,B,0
    2,2,2,2,0,0,0,L

  Style01,Male,5,6,7,8
    Arial,12,B,0
    2,2,2,2,0,0,0,L

  Style02,Female,9,10,11,12
    Arial,12,B,0
    2,2,2,2,0,0,0,L

  Style03,Other,4,8,12,14
    Arial,12,B,0
    2,2,2,2,0,0,0,L

  StyleEnd

'Margins : L,R,T,Line Spacing
  2,2,7,12

'Other: Border Colour,Detail Level
  0,2

'--- Track Information ---

Status    0
Title     {title}
Artist    {artist}
Audio     {audio_path}
BuildFile
Intro
Outro

Comments  Hacked by Matt Joy
          github.com/mattjoykaraoke

-----------------------------
LYRICSV2
{lyrics}"""

def export_auto_files(artist, song, out_dir, content, audio_path):
    """Exports both raw TXT and KBP formatted lyrics."""
    artist = artist.strip()
    song = song.strip()

    # Determine base name, falling back to 'unsynchronized' if both are empty
    if artist and song:
        base_name = f"{artist} - {song}"
    elif artist:
        base_name = artist
    elif song:
        base_name = song
    else:
        base_name = "unsynchronized"

    # Strip illegal characters from filenames
    clean_name = re.sub(r'[\\\\/*?:"<>|]', "", base_name)
    if not clean_name.strip():
        clean_name = "unsynchronized"

    txt_path = Path(out_dir) / f"{clean_name}.txt"
    kbp_path = Path(out_dir) / f"{clean_name}.kbp"

    # Save the raw .txt file
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Save the formatted .kbp file
    kbp_content = generate_kbp_content(song if song else "Unknown Title", artist if artist else "Unknown Artist", audio_path, content)
    
    # UTF-8-SIG saves with BOM, which is best for ensuring Karaoke Builder reads foreign characters properly
    with open(kbp_path, "w", encoding="utf-8-sig") as f:
        f.write(kbp_content)
        
    return txt_path, kbp_path
