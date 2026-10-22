"""A small bank of hand-written, pre-verified, natural stories
(decision 0078) -- a second-tier fallback between the LLM-generated
path (book_generation.py) and the guaranteed-decodable word-drill
(deterministic_book.py, decision 0077).

Context: decision 0077's own word-drill is honest but not satisfying
-- "Fin fit fix fizz a." is fully decodable but reads nothing like a
story. A product-owner critique of a real session named this
directly: when generation fails, prefer a pre-validated, actually-
natural story over a word list. Writing a story that is BOTH natural
AND fully decodable at a maximally restrictive budget (e.g. pure
short-vowel CVC/VC words, with no suffix -- so no third-person "-s"
verb endings at all) turned out to be genuinely hard by hand too, the
same constraint-satisfaction difficulty decision 0076 found the LLM
struggling with -- solved here by iterating against the real
decodability engine while drafting (not guessing), and by leaning on
modal constructions ("can run", not "runs") exactly the way real
decodable-reader programs do.

Each story is authored for one cumulative phonics budget level (every
level up to and including the one named, in curriculum order) -- not
one single grapheme, since hand-writing natural prose per individual
grapheme across 72 graphemes isn't a sustainable scope for this
decision. Re-verified against the real decodability engine at call
time, every time -- never trusted from authoring alone, same
discipline every other verifier in this package already follows.
"""
from dataclasses import dataclass

from .curriculum import DEFAULT_SIGHT_WORDS, LEVEL_SEQUENCE
from .decodability import clean_word, is_word_decodable
from .schema import GeneratedBook, Objective

# Same convention decodability.py's own check_decodability() already
# uses: the curriculum's default sight words are always exempt from
# grapheme-budget checking, regardless of what a caller passes --
# not a second, possibly-drifting definition of "sight word."
_DEFAULT_SIGHT = {clean_word(w) for w in DEFAULT_SIGHT_WORDS}


@dataclass(frozen=True)
class _BankStory:
    title: str
    level: str  # the LEVEL_SEQUENCE level this story was authored for
    pages: list[str]


_STORY_BANK: list[_BankStory] = [
    _BankStory(
        "Sam and the Cat",
        "short_vowels",
        ["Sam has a cat.", "The cat can nap.", "Sam can nap.", "Sam and the cat nap in the sun."],
    ),
    _BankStory(
        "Pat and the Pup",
        "short_vowels",
        ["Pat has a pup.", "The pup can run.", "Pat can run.", "Pat and the pup run and run."],
    ),
    _BankStory(
        "The Hen and the Pig",
        "short_vowels",
        ["A hen sat on a log.", "A pig ran to the hen.", "The hen and the pig had fun."],
    ),
    _BankStory(
        "The Fish and the Wish",
        "digraphs",
        ["A fish had a wish.", "The fish can dash and dash.", "The fish had fun with a wish."],
    ),
    _BankStory(
        "Chip and Beth",
        "digraphs",
        ["Chip sat on a path.", "Chip can chat.", "Beth can chat.", "Chip and Beth chat a lot."],
    ),
    _BankStory(
        "Brad and His Dog",
        "blends",
        [
            "Brad can trot on his sled.",
            "Brad and his dog trot past a pond.",
            "Brad and his dog had fun as a pal.",
        ],
    ),
    _BankStory(
        "Gran and Flip",
        "blends",
        [
            "Gran set a snack on the desk.",
            "Flip the frog can jump on the desk.",
            "Flip and Gran can snack and chat.",
        ],
    ),
    _BankStory(
        "Jane and Mike",
        "silent_e",
        [
            "Jane can bake a cake.",
            "Jane and Mike like the same cake.",
            "Jane and Mike smile and take a bite.",
        ],
    ),
    _BankStory(
        "The Mole",
        "silent_e",
        [
            "A mole made a home in a hole.",
            "The mole can poke its nose up.",
            "The mole can hide in its home.",
        ],
    ),
    _BankStory(
        "Fern and the Star",
        "r_controlled",
        [
            "A star shone far up in the dark.",
            "Fern can spot the star.",
            "Fern and her pal can star gaze.",
        ],
    ),
    _BankStory(
        "The Bird",
        "r_controlled",
        [
            "A bird sat on a yard.",
            "The bird can chirp for a snack.",
            "The bird and her pal chirp and dart.",
        ],
    ),
    _BankStory(
        "Joy at Sea",
        "vowel_teams",
        [
            "A boat can float on the sea.",
            "Joy and her team row out to the boat.",
            "Joy can see a seal in the sea.",
        ],
    ),
    _BankStory(
        "May in the Rain",
        "vowel_teams",
        [
            "Rain fell on the train each day.",
            "May and her pal play in the rain.",
            "May and her pal stay in the train.",
        ],
    ),
    _BankStory(
        "The Singing King",
        "glued_sounds",
        [
            "A king can sing a long song.",
            "The king and his pals sing and clap.",
            "The song made the king feel strong.",
        ],
    ),
    _BankStory(
        "Hank and the Ball",
        "glued_sounds",
        [
            "A small ball can roll down the hall.",
            "Hank can kick the small ball.",
            "Hank and his pal yank the ball back.",
        ],
    ),
    _BankStory(
        "The Shy Pup",
        "y_vowel",
        [
            "A shy pup can hide in the grass.",
            "My pup can run and try to fly a kite.",
            "My shy pup can fly high in the sky.",
        ],
    ),
    _BankStory(
        "The Funny Bunny",
        "y_vowel",
        [
            "A funny bunny can hop all day.",
            "My bunny can try to hop on a log.",
            "My funny bunny can spy a bug in the sky.",
        ],
    ),
    _BankStory(
        "The Frogs",
        "suffixes",
        [
            "The frogs jumped into the pond and splashed about.",
            "They looked for bugs and munched on tasty snacks.",
            "The frogs played happily until the sun started setting.",
        ],
    ),
    _BankStory(
        "The Dinosaur",
        "suffixes",
        [
            "A big dinosaur stomped through the woods looking for leaves.",
            "It spotted a tasty plant and munched it happily.",
            "Then it stretched its long neck and let out a happy roar.",
        ],
    ),
]


def _budget_for(objective: Objective) -> list[str]:
    budget = list(objective.mastered_levels)
    if objective.target_level not in budget:
        budget.append(objective.target_level)
    return budget


def _story_is_decodable_at(story: _BankStory, budget: list[str], sight: set[str]) -> bool:
    for page in story.pages:
        for raw in page.split():
            w = clean_word(raw)
            if not w or w in sight:
                continue
            if not is_word_decodable(w, budget):
                return False
    return True


def pick_story_bank_book(
    objective: Objective,
    *,
    sight_words: set[str] | None = None,
    session_index: int = 0,
) -> GeneratedBook | None:
    """Returns a hand-written, pre-verified natural story that is
    fully decodable at `objective`'s own cumulative budget, or `None`
    if none in the bank qualify (so the caller falls through to
    deterministic_book.py's guaranteed word-drill instead). Prefers a
    story authored for the objective's own target_level; falls back
    to any other qualifying story otherwise, so a more advanced
    objective still gets an appropriately-pitched story when one
    exists but is never left with nothing just because its exact
    level has none free this session_index.

    Re-verifies every candidate's decodability against the real
    engine at call time -- authoring-time correctness (checked by
    hand while writing these) is never trusted on its own, same as
    every other verifier in this package.
    """
    budget = _budget_for(objective)
    sight = set(sight_words or set()) | _DEFAULT_SIGHT
    decodable = [s for s in _STORY_BANK if _story_is_decodable_at(s, budget, sight)]
    if not decodable:
        return None

    on_level = [s for s in decodable if s.level == objective.target_level]
    pool = on_level or decodable
    chosen = pool[session_index % len(pool)]

    return GeneratedBook(
        title=chosen.title,
        pages=list(chosen.pages),
        target_grapheme=objective.target_grapheme,
        objective=objective,
        sight_words=sight,
        generation_source="story_bank",
    )
