"""Guaranteed-decodable, offline book builder (decision 0077) --
ported near-verbatim from phono-storyforge's eval/book_builder.py
(Apache 2.0), the same project decodability.py/alignment.py/mastery.py/
curriculum.py/planner.py were already ported from. That project's own
provider layer (app/tutor/book_source.py's make_llm_book_provider())
uses this exact deterministic builder as the fallback for when its
LLM generator can't converge -- the same role it plays here.

Why this, not another LLM retry: no network call, no rate limit, no
model non-determinism -- a fixed, pre-decomposed word corpus and pure
selection logic, so this function cannot raise BookGenerationError
and cannot produce an undecodable word. Reuses this package's own
decodability engine (decodability.py) as the one source of truth for
what's allowed, same as every other reading/ module.

Not a narrative story -- a short, readable word-practice passage (a
few words from the target grapheme, the spaced-review graphemes, and
decodable filler, with light sight-word connectors woven in so it
reads as text rather than a flashcard list). That's an honest,
deliberate trade against the LLM path's actual storytelling: the
point of this module is the guarantee, not the prose.
"""
import random
from dataclasses import dataclass, field

from .curriculum import GRAPHEME_INVENTORY, LEVEL_SEQUENCE
from .decodability import clean_word, decompose, inflectional_suffix, is_word_decodable
from .schema import GeneratedBook, Objective

# A pool of single-syllable decodable words spanning the phonics scope-
# and-sequence, curated (not LLM-generated) so the fallback is fixed
# and reviewable. Ported verbatim from the reference project's own
# corpus -- generic phonics vocabulary, not creative/proprietary
# content, same category as curriculum.py's own ported data.
_CORPUS_TEXT = """
cat hat map bat rat sat fat mat pad sad mad bad dad had bag tag rag wag nag jam ham yam ram
can man pan ran fan tan tap lap nap cap gap wax tax cab nab lab dab gas
bed red led fed wed beg leg peg hen pen ten den men net pet vet jet wet get let met set web egg
big pig dig fig wig win pin fin tin bin sit fit hit kit lit pit bit dim rim him fix mix six
hot pot dot got lot not cot top mop hop cop pop log dog fog jog box fox cob job rob sob nod rod cod
sun run bun fun gun nun cup pup cut gut hut nut but bug rug mug jug hug tug tub cub rub mud bud
zip zap zig zag buzz fizz fuzz jazz zigzag
shop ship shed shot fish dish wish cash dash rash gash mash hush rush shut
chip chop chin chat chum chug chap rich much such
thin this that then them thud bath path math with moth
whip whiz when whim
duck sock rock lock kick pick sick lick neck deck peck back pack sack tack rack
quit quiz
stop step spin spit spot snap slap clap clip flap flag flat plan plot plug glad grab grin trap trip
drum drop frog from crab crib club blob slim swim twin twig
fast last list must dust nest test best rest milk silk help yelp belt melt felt jump bump lump
hand land sand band bend send lend pond fond hint mint tent rent went sent lift gift sift soft
cake bake lake make take wake game name same came fame lane cane mane plane grape
bike like hike bite kite mile pile time lime dime fine line mine nine vine wide ride side hide
hope rope note rose nose home bone cone stone slope
cube tube cute mute use rule mule eve theme these
car bar far jar tar star scar hard card yard farm harm arm art cart part dart
her herd fern term
bird girl
for fork corn born torn cord sort port short storm
fur turn burn hurt curl surf
rain main pain wait paid tail nail sail mail jail rail snail train
day say way play stay clay tray gray
see bee tree free feet meet seed need deed week keep deep sleep green
eat seat meat beat heat read leaf team bean mean clean dream
boat coat road soap goat load toad
toe doe
pie tie die lie
high night light right sight might fight tight bright
moon soon zoo food mood room boot root tooth
out loud cloud mouth round found sound ground proud
cow now how down town brown crown clown
boil coil soil oil join coin point
boy toy joy
saw paw jaw law claw draw straw
haul fault haunt vault
all ball call fall hall mall tall wall small
bank tank rank sank thank drank blank
pink link sink wink think drink blink
king sing ring wing thing bring sting swing
song long gong strong
hung rung lung sung stung
honk bonk conk
junk sunk bunk trunk skunk
bang rang sang hang gang fang
my by fly try sky shy spy cry dry sly fry
happy puppy funny sunny bunny silly jelly belly penny daddy muddy
cats dogs pigs hats maps bugs cups beds pens
boxes foxes dishes wishes
jumped helped landed wanted napped
jumping helping running sitting reading
"""

# Light decodable/sight connectors so a page reads like text rather
# than a word list. Sight words for the learner -- no grapheme
# evidence is attributed to them (they're added to `sight_words`
# below, same as the exercise/book-generation paths already do for
# their own connector words).
_CONNECTORS = ["the", "a", "and", "is", "can", "on", "in", "it"]

# Words per page -- short enough to read in one capture, consistent
# with how short this mode's other generated/uploaded content already
# is per page/sentence.
_WORDS_PER_PAGE = 5


def _build_corpus() -> list[str]:
    seen: set[str] = set()
    words: list[str] = []
    for w in _CORPUS_TEXT.split():
        d = decompose(w, mastered_levels=LEVEL_SEQUENCE)
        if d.is_decodable and d.word not in seen:
            seen.add(d.word)
            words.append(d.word)
    return words


CORPUS: list[str] = _build_corpus()


def _grapheme_keys(word: str) -> set[str]:
    """All inventory keys a word exercises, including the structural
    sentinels -- same logic book_generation.py's own _grapheme_keys()
    already uses, duplicated rather than imported since this module
    stays entirely self-contained (no LLM-path dependency at all)."""
    d = decompose(word)
    keys = {g.grapheme for g in d.graphemes}
    gs = d.graphemes
    if any(gs[i].kind == "C" and gs[i + 1].kind == "C" for i in range(len(gs) - 1)):
        keys.add("_blend_")
    suffix = inflectional_suffix(d.word)
    if suffix:
        keys.add(f"-{suffix}")
    return keys


_INDEX: dict[str, list[str]] = {}
for _w in CORPUS:
    for _k in _grapheme_keys(_w):
        _INDEX.setdefault(_k, []).append(_w)
for _k in _INDEX:
    _INDEX[_k] = sorted(set(_INDEX[_k]))


def _level_budget(level: str) -> list[str]:
    return LEVEL_SEQUENCE[: LEVEL_SEQUENCE.index(level) + 1]


def _compute_unteachable() -> frozenset[str]:
    """Graphemes with no decodable single-syllable word in this corpus
    at their own introduction budget -- exposed for a future planner
    improvement (skip straight past a grapheme this corpus can never
    exercise), not yet consulted by planner.py in this decision."""
    unteachable: set[str] = set()
    for grapheme, level in GRAPHEME_INVENTORY:
        budget = _level_budget(level)
        words = _INDEX.get(grapheme, [])
        if not any(is_word_decodable(w, budget) for w in words):
            unteachable.add(grapheme)
    return frozenset(unteachable)


UNTEACHABLE_GRAPHEMES: frozenset[str] = _compute_unteachable()


def _target_words(objective: Objective) -> list[str]:
    budget = list(objective.mastered_levels)
    if objective.target_level not in budget:
        budget.append(objective.target_level)
    return [w for w in _INDEX.get(objective.target_grapheme, []) if is_word_decodable(w, budget)]


def _decodable_filler(budget: list[str]) -> list[str]:
    return [w for w in CORPUS if is_word_decodable(w, budget)]


def _source_passage_words(source_passage: str, budget: list[str]) -> list[str]:
    """Decision 0077: words from the parent's own uploaded exercise
    that happen to already be decodable at the current budget --
    preferred over the generic corpus for filler, so a guaranteed-
    decodable fallback still has a loose thread back to what the
    child was actually just reading, instead of unrelated drill
    words every time."""
    seen: set[str] = set()
    words: list[str] = []
    for raw in source_passage.split():
        cleaned = clean_word(raw)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        if is_word_decodable(cleaned, budget):
            words.append(cleaned)
    return words


def _rotate(words: list[str], n: int, *, session_index: int, rng: random.Random | None) -> list[str]:
    """Deterministically picks n words, rotating by session for
    variety -- an optional seeded rng only varies which words are
    drawn, never decodability."""
    if not words:
        return []
    if rng is not None:
        pool = list(words)
        rng.shuffle(pool)
        return pool[:n]
    offset = session_index % len(words)
    return [words[(offset + i) % len(words)] for i in range(n)]


def _chunk_into_pages(words: list[str]) -> list[str]:
    """Groups a flat word list into short, capitalized, period-ended
    "pages" -- not grammatical prose (this is a decodable word-
    practice passage, not a narrative), but matches the shape every
    other part of this pipeline expects (GeneratedBook.pages,
    sentences.split_into_sentences()'s own terminal-punctuation
    boundaries) so the rest of Reading Partner works on it unchanged."""
    pages: list[str] = []
    for i in range(0, len(words), _WORDS_PER_PAGE):
        chunk = words[i : i + _WORDS_PER_PAGE]
        if not chunk:
            continue
        line = " ".join(chunk)
        pages.append(line[0].upper() + line[1:] + ".")
    return pages


def build_deterministic_book(
    objective: Objective,
    *,
    session_index: int = 0,
    num_target: int = 6,
    length: int = 16,
    sight_words: set[str] | None = None,
    rng: random.Random | None = None,
    interest: str = "",
    source_passage: str | None = None,
) -> GeneratedBook:
    """Builds a decodable practice passage for `objective` that is
    guaranteed to be fully decodable -- no LLM call, so this cannot
    raise BookGenerationError and cannot fail decodability. Composed
    of: several words exercising the target grapheme, one word per
    spaced-review grapheme, decodable filler (preferring words from
    `source_passage` where they're already decodable) to reach
    `length`, and sight-word connectors woven in every few words so
    it reads as text rather than a word list.

    `interest` (decision 0077, e.g. "dinosaurs," parent-set on
    ChildProfile) only ever flavors the TITLE -- titles aren't
    decodability-checked anywhere in this package, but the body text
    must stay inside budget, and real thematic vocabulary like
    "dinosaur" itself is almost never decodable at the earliest
    levels this fallback exists for. Dressing up the title is honest
    personalization; pretending the body is themed would not be.
    """
    budget = list(objective.mastered_levels)
    if objective.target_level not in budget:
        budget.append(objective.target_level)

    sight = set(sight_words or set()) | set(_CONNECTORS)

    targets = _target_words(objective)
    chosen_targets = _rotate(targets, num_target, session_index=session_index, rng=rng) if targets else []

    review: list[str] = []
    for g in objective.review_graphemes:
        cands = [w for w in _INDEX.get(g, []) if is_word_decodable(w, budget)]
        if cands:
            review.append(_rotate(cands, 1, session_index=session_index, rng=rng)[0])

    body = chosen_targets + review
    if len(body) < length:
        preferred_pool = (
            [w for w in _source_passage_words(source_passage, budget) if w not in set(body)]
            if source_passage
            else []
        )
        filler_pool = preferred_pool + [
            w for w in _decodable_filler(budget) if w not in set(body) and w not in preferred_pool
        ]
        body += _rotate(filler_pool, length - len(body), session_index=session_index, rng=rng)

    words: list[str] = []
    for i, w in enumerate(body):
        if i > 0 and i % 4 == 0:
            words.append(_CONNECTORS[(i // 4) % len(_CONNECTORS)])
        words.append(w)

    title = f"{interest.strip().title()} Word Time!" if interest.strip() else f"The {objective.target_grapheme.upper()} Words"

    return GeneratedBook(
        title=title,
        pages=_chunk_into_pages(words),
        target_grapheme=objective.target_grapheme,
        objective=objective,
        sight_words=sight,
        generation_source="deterministic_fallback",
    )
