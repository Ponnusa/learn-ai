"""Word-family generalization check (decision 0066) -- once a word is
read successfully, offer a small set of same-pattern words (same
rime, different onset: mat -> cat, sat, bat, rat) so the child's skill
is tested against new words, not just the one just read.

Same verifier-gated shape every other generation path in this package
uses (book_generation.py's decodability retry loop, comprehension.py's
screen-and-drop): the LLM *proposes* candidate words, but whether a
candidate actually shares the target rime, is decodable at the
child's current level, AND is a real word (decision 0073) is a
deterministic check, not something trusted on the model's say-so. A
candidate that fails any check is simply dropped -- there's no
single "fix" for a bad rhyme the way there is for a decodability
violation, so this follows comprehension.py's simpler screen-and-drop
precedent, not book_generation.py's heavier feed-back-and-retry loop.

Decision 0073, found live: asked for words rhyming with "frog," the
LLM returned "prog," "brog," "srog" -- invented, not real. Two
compounding causes, both fixed here: (1) the onset-rime split
originally treated only "frog"'s first letter as the onset, giving
rime "rog" -- a pattern almost no real word shares, so the model had
nothing genuine to offer and filled in rhyming nonsense instead;
_rime_graphemes() now splits on the first VOWEL grapheme instead (the
standard linguistic definition), so "frog" correctly gets onset "fr"
and rime "og" (dog, fog, hog, jog, log, ...), which has real matches.
(2) Even with a correct rime, nothing checked that a candidate was an
actual word at all -- verify_family_word() now also requires
membership in _COMMON_ENGLISH_WORDS, an originally-assembled (not
externally-sourced -- see its own comment for why) list of common,
simple, real English words.
"""
from .decodability import GraphemeHit, clean_word, decompose, is_word_decodable

# Decision 0073, found live: verify_family_word() originally checked
# only phonics STRUCTURE (exact rime match + decodable) -- real-word-
# ness was never checked at all. Asked for words rhyming with "frog,"
# the LLM returned "prog," "brog," "srog" -- each one phonics-
# structurally valid (same rime, decodable CVC-with-blend shape) but
# not real English words, and the verifier waved every one through.
# This is an originally-assembled list of common, simple, real
# English words covering the classic phonogram/word-family groups
# used throughout early-reading pedagogy (short vowels, digraphs,
# blends, silent-e, r-controlled vowels, vowel teams, glued sounds,
# y-as-a-vowel) -- not copied from any single external wordlist or
# corpus, specifically to avoid this child-safety product inheriting
# an external dataset's licensing terms (several well-known
# candidates, checked and rejected: Google's n-gram-derived word
# lists explicitly discourage commercial use without separately
# licensing the underlying corpus from the LDC). Deliberately not
# exhaustive -- a real, decodable word missing from this list is
# simply dropped (same "fails a check -> drop, don't retry" shape
# every other verifier in this package already follows), never
# treated as an error. Missing real coverage is an acceptable false
# negative; a word a child has never seen before, invented by an LLM,
# is not an acceptable false positive.
_COMMON_ENGLISH_WORDS: frozenset[str] = frozenset(
    " ".join(
        [
            "a i am an as at ax us",  # short standalone words
            "cab dab jab lab nab tab crab grab stab",  # -ab
            "back hack jack lack pack rack sack tack black crack track "
            "snack stack quack shack smack",  # -ack
            "bad dad had lad mad pad sad glad",  # -ad
            "bag gag hag lag nag rag sag tag wag brag drag flag snag",  # -ag
            "fail jail mail nail pail rail sail tail trail snail",  # -ail
            "main pain rain gain vain chain brain train plain stain grain",  # -ain
            "bake cake lake make rake sake take wake brake flake shake snake stake",  # -ake
            "bale gale male pale sale tale scale whale",  # -ale
            "came fame game name same tame blame flame frame shame",  # -ame
            "camp damp lamp ramp champ clamp cramp stamp tramp",  # -amp
            "ban can fan man pan ran tan van clan plan scan span",  # -an
            "band hand land sand grand stand",  # -and
            "bang gang hang rang sang clang",  # -ang
            "bank rank sank tank yank blank crank drank frank plank thank",  # -ank
            "cap gap lap map nap rap sap tap zap clap flap slap snap trap wrap",  # -ap
            "cash dash gash hash mash rash sash bash clash crash flash smash splash trash",  # -ash
            "ask bask mask task",  # -ask
            "bat cat fat hat mat pat rat sat vat chat flat that",  # -at
            "date fate gate hate late mate rate crate plate skate slate state",  # -ate
            "jaw law paw raw saw claw draw straw",  # -aw
            "box fax wax tax",  # -ax
            "bay day hay jay lay may pay ray say way clay gray play stay tray",  # -ay
            "beat heat meat neat seat feat wheat treat cheat",  # -eat
            "deck neck peck check wreck",  # -eck
            "bed fed led red wed bred fled sled sped",  # -ed
            "beg leg peg",  # -eg
            "bell cell sell tell well fell shell smell spell swell",  # -ell
            "belt felt melt",  # -elt
            "den hen men pen ten when then",  # -en
            "bend lend send tend blend spend",  # -end
            "bent dent rent sent tent went spent",  # -ent
            "best nest pest rest test vest west chest crest",  # -est
            "bet get jet let met net pet set vet wet",  # -et
            "dice mice nice rice vice slice spice twice",  # -ice
            "kick lick pick sick tick brick chick click stick thick trick",  # -ick
            "did hid kid lid rid",  # -id
            "hide ride side tide wide bride glide slide pride",  # -ide
            "big dig fig jig pig rig wig",  # -ig
            "fight light might night right sight tight bright flight fright",  # -ight
            "mile pile tile file smile while",  # -ile
            "bill fill hill mill pill will chill drill grill skill spill still thrill",  # -ill
            "dim him rim",  # -im
            "bin fin pin tin win chin grin shin skin spin thin twin",  # -in
            "dine fine line mine nine pine vine wine shine spine swine",  # -ine
            "king ring sing wing bring sting swing thing",  # -ing
            "link pink rink sink wink blink drink stink think",  # -ink
            "dip hip lip rip sip tip zip chip clip drip flip grip ship skip slip trip whip",  # -ip
            "bit fit hit kit pit sit wit grit quit spit",  # -it
            "dive five give hive live",  # -ive
            "bob cob job mob rob sob",  # -ob
            "dock lock rock sock clock block flock knock shock stock",  # -ock
            "cod nod pod rod",  # -od
            "dog fog hog jog log",  # -og
            "joke poke woke broke choke smoke spoke stroke",  # -oke
            "bold cold fold gold hold sold told",  # -old
            "hole mole pole role",  # -ole
            "bone cone tone zone alone phone stone",  # -one
            "hop mop pop top chop crop drop shop stop",  # -op
            "core more sore tore wore chore score shore snore store swore",  # -ore
            "cot dot got hot jot lot not pot rot tot",  # -ot
            "cub rub sub tub club grub scrub stub",  # -ub
            "buck duck luck suck tuck chuck stuck truck",  # -uck
            "bug dug hug jug mug rug tug drug plug slug snug",  # -ug
            "gum hum mum sum chum drum plum",  # -um
            "bump dump hump jump lump pump clump grump stump thump",  # -ump
            "bun fun gun nun run sun stun",  # -un
            "bunk dunk hunk junk sunk chunk drunk skunk trunk honk",  # -unk/-onk
            "but cut gut hut nut",  # -ut
            "ship shed shell shut shin fish wish dish",  # sh-
            "much such rich",  # -ch (onset already covered via chip/chat/chin/chop above)
            "this than with path math bath",  # th-
            "what when why whip",  # wh-
            "song long strong wrong rung sung gong",  # -ong/-ung (glued sounds)
            "small ball call fall tall wall",  # -all (glued sounds)
            "car far jar star scar bar",  # -ar (r-controlled)
            "her per",  # -er (r-controlled)
            "sir stir bird girl",  # -ir (r-controlled)
            "for nor corn born torn worn",  # -or (r-controlled)
            "fur cur blur",  # -ur (r-controlled)
            "bee see tree free green seed need feel feet",  # -ee (vowel team)
            "sea tea pea read team leaf",  # -ea (vowel team)
            "boat coat goat road soap",  # -oa (vowel team)
            "moon soon boot food book look good foot",  # -oo (vowel team)
            "out loud cloud round found sound",  # -ou (vowel team)
            "cow how now bow",  # -ow (vowel team)
            "oil boil coin soil",  # -oi (vowel team)
            "boy toy joy",  # -oy (vowel team)
            "sauce pause cause",  # -au (vowel team)
            "these theme",  # e_e (silent e)
            "like time five bike ride nice side wide",  # i_e (silent e)
            "home rope hope note nose those woke",  # o_e (silent e)
            "cube tube cute use",  # u_e (silent e)
            "my by fly sky cry dry try shy why",  # y as long i
            "happy funny baby candy lucky puppy bunny sunny silly",  # y as long e
            "jumped played looked wanted",  # -ed suffix
            "cats dogs pigs pens hens boxes wishes",  # -s/-es suffix
            "dog pig pot big red leg pen ten hen web met mud cup",  # extra common short-vowel words
        ]
    ).split()
)


def _rime_graphemes(graphemes: list[GraphemeHit]) -> list[GraphemeHit] | None:
    """The standard linguistic onset-rime split: the onset is
    everything before the first VOWEL-kind grapheme (a single
    consonant, e.g. "m" in "mat," or a full blend, e.g. "fr" in
    "frog") -- the rime is that first vowel onward. Decision 0073,
    found live: the original version always treated only the single
    first grapheme as the onset, so "frog" (f-r-o-g) got rime "rog"
    instead of the real "og" -- a pattern essentially no other real
    English word shares, which is exactly why the LLM asked to match
    it invented "prog"/"brog"/"srog" rather than admit none exist.
    "og" (dog, fog, hog, jog, log, clog, ...) has many real matches.
    None if there's no vowel to anchor on, or the word starts with one
    (e.g. "at") -- nothing meaningful to treat as a separate onset."""
    first_vowel_idx = next((i for i, g in enumerate(graphemes) if g.kind == "V"), None)
    if not first_vowel_idx:  # None (no vowel) or 0 (word starts with the vowel itself)
        return None
    return graphemes[first_vowel_idx:]


def extract_rime(word: str) -> tuple[str, list[GraphemeHit]] | None:
    """Splits `word` into its onset and rime (see _rime_graphemes()),
    returning the rime's plain spelling alongside its structured
    graphemes -- the spelling for the LLM prompt, the graphemes for
    verify_family_word()'s exact-match check. None for a word with
    only one grapheme (e.g. "a") or no onset-rime split to make."""
    graphemes = decompose(word).graphemes
    if len(graphemes) <= 1:
        return None
    rime_graphemes = _rime_graphemes(graphemes)
    if rime_graphemes is None:
        return None
    rime_spelling = "".join(g.grapheme for g in rime_graphemes)
    return rime_spelling, rime_graphemes


def build_family_prompt(word: str, rime_spelling: str, num_words: int = 4) -> str:
    """Asks for simple, real, same-pattern words sharing `word`'s rime
    -- same `WORD:`-per-line convention as every other generation
    prompt in this codebase (book_generation.py, comprehension.py)."""
    return (
        "You are Chitti, a friendly companion robot helping a child practice "
        f'phonics. A child just read the word "{word}" correctly. Write '
        f"{num_words} other simple, real English words that end in \"-{rime_spelling}\", "
        f'the same way "{word}" does -- just a different starting sound or letter. '
        "Use only common, simple words a young child would already know.\n\n"
        'Reply with exactly one word per line, each starting with "WORD:", nothing else.'
    )


def parse_family_words(reply_text: str) -> list[str]:
    """Parses the WORD:-per-line format build_family_prompt() asks
    for. Same strict-but-forgiving style as comprehension.py's
    parse_questions()."""
    words: list[str] = []
    for line in reply_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("WORD:"):
            word = line.split(":", 1)[1].strip()
            if word:
                words.append(word)
    return words


def verify_family_word(
    candidate: str, target_rime_graphemes: list[GraphemeHit], mastered_levels: list[str]
) -> bool:
    """True only if `candidate` actually shares the target rime --
    exactly the same grapheme sequence after its own onset, not just
    an approximate rhyme -- is decodable at the child's current
    phonics budget, AND is a real word (decision 0073: phonics
    structure alone isn't enough -- "prog"/"brog"/"srog" all share
    "frog"'s rime and are perfectly decodable, but aren't words).
    Any check failing drops the candidate."""
    cleaned = clean_word(candidate)
    if cleaned not in _COMMON_ENGLISH_WORDS:
        return False
    candidate_graphemes = decompose(cleaned).graphemes
    candidate_rime_graphemes = _rime_graphemes(candidate_graphemes)
    if candidate_rime_graphemes is None:
        return False
    candidate_rime = [g.grapheme for g in candidate_rime_graphemes]
    target_rime = [g.grapheme for g in target_rime_graphemes]
    if candidate_rime != target_rime:
        return False
    return is_word_decodable(cleaned, mastered_levels)
