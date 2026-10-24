"""Decision 0104: a vendored library of pre-written, already-leveled
reading-partner stories -- a parent-selectable alternative to both
the LLM-generated path (book_generation.py) and the "write your own"
reading-exercises upload (parent_controls/reading_exercises.py).
Most parents never use the upload path at all (writing a story by
hand is real effort); picking a phase and getting an already-written
story back is far less friction.

Sourced from github.com/jonajinga/open-phonics ("Open Phonics" -- a
free, open-source phonics app teaching reading via the Direct
Instruction methodology developed by Siegfried Engelmann, built by
Pikes Peak Web Designs). That project's own LICENSE is MIT. Used here
with the user's own explicit confirmation they additionally hold the
rights to copy this content -- same sourcing-and-rights documentation
precedent decision 0091 already established for the real phonics
sound clips (state the source, state the license, state the user's
own rights representation, then proceed).

All 30 stories currently in that project's `src/stories/*.md` are
vendored verbatim below (markdown bold markers around target words
stripped; paragraph breaks become one page each) -- a one-time
conversion, not a runtime markdown/YAML dependency. Each story's own
`phase` (1-7) and `order` come directly from that project's own
frontmatter. Deliberately NOT re-verified against this codebase's own
decodability.py budget the way story_bank.py's hand-written stories
are: this content is already vetted by its own authors at its own
phase, and a parent who explicitly picked that phase made a
deliberate choice this module shouldn't second-guess. Mastery
attribution still works unchanged regardless -- assess()/
attribute_evidence() decompose whatever text they're given against
this codebase's own grapheme inventory, independent of which
taxonomy originally classified the source.
"""
from dataclasses import dataclass

from .schema import GeneratedBook, Objective

# Decision 0104: brief, parent-facing phase metadata for the Parent
# Controls "starting phase" picker -- titles/subtitles straight from
# the source project's own src/_data/phases.js, not reinvented here.
PHASES: list[tuple[int, str, str]] = [
    (1, "Phase 1: Foundation", "Lessons 1-20 -- first sounds and blending"),
    (2, "Phase 2: Building", "Lessons 21-40 -- digraphs, long vowels, sight words"),
    (3, "Phase 3: Expanding", "Lessons 41-75 -- remaining sounds, r-controlled vowels"),
    (4, "Phase 4: Vowel Teams", "Lessons 76-88 -- ea, ee, oa, ay, ai"),
    (5, "Phase 5: Patterns & Rules", "Lessons 89-100 -- diphthongs, ck, unvoiced th"),
    (6, "Phase 6: Blends & Advanced", "Lessons 101-125 -- consonant blends, -ed, soft c/g"),
    (7, "Phase 7: Mastery", "Lessons 126-150 -- remaining blends, suffixes, syllables"),
]


@dataclass(frozen=True)
class LibraryStory:
    slug: str
    title: str
    phase: int
    order: int
    pages: list[str]
    comprehension: list[tuple[str, str]]


_LIBRARY_STORIES: list[LibraryStory] = [
    LibraryStory(
        slug='sam-sat',
        title='Sam Sat',
        phase=1,
        order=1,
        pages=['Sam sat.', 'Sam sat at the mat.', 'A rat sat at the mat.', 'Sam is mad at the rat.'],
        comprehension=[('Where did Sam sit?', 'Sam sat at the mat.'), ('Who else sat at the mat?', 'A rat sat at the mat.'), ('How did Sam feel about the rat?', 'Sam is mad at the rat.')],
    ),
    LibraryStory(
        slug='the-cat-at-the-mat',
        title='The Cat at the Mat',
        phase=1,
        order=2,
        pages=['The cat is at the mat.', 'The rat is at the mat.', 'The cat is mad.', 'The rat is sad.', 'The cat sat. The rat sat.'],
        comprehension=[('Who sat at the mat first?', 'The cat sat at the mat.'), ('How did the cat feel?', 'The cat is mad.'), ('What did the rat do?', 'The rat rid the mat.')],
    ),
    LibraryStory(
        slug='it-is-dim',
        title='It Is Dim',
        phase=1,
        order=3,
        pages=['It is dim.', 'Sam sat in the mist.', 'A rat rid this mat.', 'Sam is sad. That is it.'],
        comprehension=[('What was it like?', 'It is dim and there is mist.'), ('Who sat in the mist?', 'Sam sat in the mist.')],
    ),
    LibraryStory(
        slug='the-man-and-the-dog',
        title='The Man and the Dog',
        phase=2,
        order=4,
        pages=['A man had a dog.', 'The dog was not a good dog.', 'The dog ran in the mud.', 'The dog dug and dug.', 'The dog got mud on the rug!', '"Not the rug!" the man said.', 'The dog sat on the man.', 'The man got mud on him too!', '"You are fun," the man said. "But you are a mud dog!"'],
        comprehension=[('Was the dog a good dog?', 'No, the dog was not a good dog.'), ('What did the dog get mud on?', 'The dog got mud on the rug.'), ('What did the man call the dog?', 'A mud dog!')],
    ),
    LibraryStory(
        slug='i-will-not-fall',
        title='I Will Not Fall',
        phase=2,
        order=5,
        pages=['"I will not fall," I said.', 'I ran to the hill.', 'I got to the hill.', '"I did it!" I said.', 'I sat on the hill.'],
        comprehension=[('Where did the reader run to?', 'To the hill.'), ('Did the reader fall?', 'No, the reader did not fall.')],
    ),
    LibraryStory(
        slug='the-fish-in-the-dish',
        title='The Fish in the Dish',
        phase=2,
        order=6,
        pages=['The fish is in the dish.', 'A man got the fish.', '"I will shut the lid," the man said.', 'The fish is fun.', 'The man and the fish sat.'],
        comprehension=[('Where is the fish?', 'The fish is in the dish.'), ('What did the man do with the lid?', 'He shut the lid.')],
    ),
    LibraryStory(
        slug='a-hat-for-the-man',
        title='A Hat for the Man',
        phase=2,
        order=7,
        pages=['The man had a hat.', 'The dog got the hat.', 'The man is mad.', 'The dog ran with the hat.', 'The man ran at the dog.', 'The man got his hat.'],
        comprehension=[('Who took the hat?', 'The dog got the hat.'), ('What did the man do?', 'The man ran at the dog to get his hat.'), ('Did the man get the hat back?', 'Yes, the man got his hat.')],
    ),
    LibraryStory(
        slug='the-red-bed',
        title='The Red Bed',
        phase=3,
        order=8,
        pages=['Ben had a red bed.', 'The bed is big.', 'His pet bit the bed.', '"Bad pet!" Ben.', 'Ben let his pet on the red bed.'],
        comprehension=[('What color was the bed?', 'The bed was red.'), ('What did the pet do to the bed?', 'The pet bit the bed.'), ('Did Ben let the pet stay on the bed?', 'Yes, Ben let his pet on the red bed.')],
    ),
    LibraryStory(
        slug='the-king-and-the-ring',
        title='The King and the Ring',
        phase=3,
        order=9,
        pages=['The king had a big ring.', 'One day the ring fell off his hand.', '"My ring! My ring is gone!" the king said.', 'The king told his men to look for it.', 'The men did look and look.', 'One man found the ring in the mud.', '"I got it!" the man said.', 'The king put the ring on his hand.', 'He was so glad he did sing a song.', 'All the men did sing with the king.'],
        comprehension=[('What did the king lose?', 'The king lost his big ring.'), ('Where was the ring found?', 'The ring was found in the mud.'), ('What did the king do when he got the ring back?', 'He sang a song.')],
    ),
    LibraryStory(
        slug='the-jar',
        title='The Jar of Jam',
        phase=3,
        order=10,
        pages=['Jim had a jar of jam.', 'But the jar was up far too high!', 'Jim got on a big box.', 'He got on his tip toes.', 'He got the jar!', 'But then — he fell off the box!', 'The jar of jam fell too.', 'Jam got on Jim. Jam got on the rug.', 'Jam got on the cat!', '"Yum!" said Jim. He ate the jam off his hand.', 'The cat ate the jam off the rug.'],
        comprehension=[('What did Jim want?', 'Jim wanted the jar of jam.'), ('What happened when Jim fell?', 'Jam got on Jim, the rug, and the cat.'), ('Who ate the jam off the rug?', 'The cat ate the jam off the rug.')],
    ),
    LibraryStory(
        slug='my-pet',
        title='My Pet',
        phase=3,
        order=11,
        pages=['My pet is a cat.', 'Her name is Moon.', 'Moon is fun.', 'Moon can run and run.', 'Moon sits on my bed at the end of the day.', 'I love my pet Moon.'],
        comprehension=[('What is the pet?', 'The pet is a cat named Moon.'), ('What can Moon do?', 'Moon can run and run.'), ('Where does Moon sit at the end of the day?', 'Moon sits on the bed.')],
    ),
    LibraryStory(
        slug='when-i-ride',
        title='When I Ride',
        phase=3,
        order=12,
        pages=['When I ride my bike, I go far.', 'I ride by the park.', 'I ride by the shop.', 'I ride and ride until it is time to go.', 'Riding is fun.'],
        comprehension=[('What does the reader ride?', 'A bike.'), ('Where does the reader ride by?', 'By the park and by the shop.'), ('Is riding fun?', 'Yes, riding is fun.')],
    ),
    LibraryStory(
        slug='the-rain',
        title='The Rain',
        phase=4,
        order=13,
        pages=['The rain came.', 'I read a book on my seat.', 'My pal ate a meal.', 'We waited for the rain to end.', 'The sun came. We ran to the tail of the road.', 'We had a real good time.'],
        comprehension=[('What happened when it rained?', 'The reader read a book on a seat.'), ('What did the reader do when the rain stopped?', 'Ran to the tail of the road.')],
    ),
    LibraryStory(
        slug='the-team',
        title='The Team',
        phase=4,
        order=14,
        pages=['Dean and Jean are a team.', 'Dean can read and read.', 'Jean can leap far.', 'One day the rain came.', '"Wait!" said Dean. "I can read to you."', 'So Dean read a tale to Jean.', 'Jean said, "That was the best tale!"', 'A good team can do a lot.'],
        comprehension=[('What can Dean do?', 'Dean can read and read.'), ('What can Jean do?', 'Jean can leap far.'), ('What did the team do in the rain?', 'The team had to wait.')],
    ),
    LibraryStory(
        slug='mail-for-me',
        title='Mail for Me',
        phase=4,
        order=15,
        pages=['The mail came at noon.', '"Is the mail for me?"', 'A letter had my name on it.', 'I read the letter.', '"Dear pal, I aim to see you," it said.', 'I sat to read it all.'],
        comprehension=[('What came at noon?', 'The mail came at noon.'), ('Who was the letter from?', 'The letter was from a pal.'), ('What did the letter say?', 'Dear pal, I aim to see you.')],
    ),
    LibraryStory(
        slug='the-loud-sound',
        title='The Loud Hound',
        phase=5,
        order=16,
        pages=['I heard a loud sound.', 'I looked out the door.', 'A big hound was running round and round the yard!', 'He ran so fast his ears went up and out.', 'Then he stopped. He put his nose on the ground.', 'He found something! A mouse!', 'The mouse ran. The hound ran.', 'The mouse hid. The hound could not find it.', 'The hound sat down and let out a loud howl.', 'I think the mouse won.'],
        comprehension=[('What was making the loud sound?', 'A big hound was running round and round.'), ('What did the hound find?', 'The hound found a mouse.'), ('Who won — the hound or the mouse?', 'The mouse won because the hound could not find it.')],
    ),
    LibraryStory(
        slug='out-and-about',
        title='Out and About',
        phase=5,
        order=17,
        pages=['I went out of the house.', 'I found a round rock on the ground.', 'I shouted, "Look at this!"', 'My pal came running out.', 'We counted the rocks we had found.', 'We found four round rocks in all.'],
        comprehension=[('What did the reader find on the ground?', 'A round rock.'), ('How many round rocks did they find?', 'Four round rocks.')],
    ),
    LibraryStory(
        slug='the-frog-and-the-crab',
        title='The Frog and the Crab',
        phase=6,
        order=18,
        pages=['A frog sat on a flat rock.', 'A crab crept from the creek.', '"What are you doing?" said the frog.', '"I am looking for a snack," said the crab.', 'The frog did a big flip into the stream.', 'Splash! The crab got wet.', '"Do it again!" said the crab.'],
        comprehension=[('What was the crab looking for?', 'The crab was looking for a snack.'), ('What did the frog do?', 'The frog did a big flip into the stream.'), ('Did the crab want the frog to do it again?', 'Yes! The crab said "Do it again!"')],
    ),
    LibraryStory(
        slug='a-bright-night',
        title='A Bright Night',
        phase=6,
        order=19,
        pages=['The night was bright with stars.', 'I could see the light from the moon.', '"What a sight!" I said.', 'A flight of birds went past.', 'I sat on the grass and watched the sky.', 'The night was still and right for dreaming.'],
        comprehension=[('What made the night bright?', 'Stars and the light from the moon.'), ('What went past in the sky?', 'A flight of birds.'), ('What was the night good for?', 'Dreaming.')],
    ),
    LibraryStory(
        slug='the-snowman',
        title='The Snowman',
        phase=6,
        order=20,
        pages=['The snow fell slow and soft.', 'I knew it was time to go out.', 'I threw on my coat and gloves.', 'I made a snowman in the yard.', 'He had a brown hat and a long scarf.', 'A few crows sat on his arms.', '"I know you will melt," I said, "but for now, you are my friend."'],
        comprehension=[('What did the reader make?', 'A snowman in the yard.'), ('What sat on the snowman?', 'A few crows sat on his arms.'), ('Will the snowman last forever?', 'No, the reader knows he will melt.')],
    ),
    LibraryStory(
        slug='joy-and-the-toy',
        title='Joy and the Toy',
        phase=6,
        order=21,
        pages=['Joy went to the toy shop.', 'She saw coins and trains and dolls.', '"Which toy do you enjoy the most?" said Mom.', 'Joy pointed at a small drum.', '"That one!" she said with a smile.', 'She joined the line to pay.', 'Joy played her drum all the way home.'],
        comprehension=[('Where did Joy go?', 'Joy went to the toy shop.'), ('What toy did Joy pick?', 'Joy pointed at a small drum.'), ('What did Joy do on the way home?', 'Joy played her drum all the way home.')],
    ),
    LibraryStory(
        slug='the-knight',
        title='The Knight',
        phase=6,
        order=22,
        pages=['The knight could write.', 'He wrote on a scroll with a quill.', 'He knew all the words in the land.', "One day he knocked on the king's door.", '"I have written you a letter," said the knight.', 'The king read the letter and smiled.', '"Kneel and I will make you my scribe."'],
        comprehension=[('What could the knight do?', 'The knight could write.'), ('What did the knight write for the king?', 'A letter.'), ('What did the king make the knight?', 'The king made him his scribe.')],
    ),
    LibraryStory(
        slug='the-straw-hat',
        title='The Straw Hat',
        phase=6,
        order=23,
        pages=['I saw a straw hat on the wall.', 'I put it on and walked outside.', 'The sun was hot and the sky was bright.', 'I drew a picture on the path with chalk.', 'A small hawk flew past.', 'I sat in the shade and yawned.', 'The straw hat kept the sun off my face.'],
        comprehension=[('What did the reader find on the wall?', 'A straw hat.'), ('What did the reader draw?', 'A picture on the path with chalk.'), ('What flew past?', 'A small hawk.')],
    ),
    LibraryStory(
        slug='the-kitten-and-the-rabbit',
        title='The Kitten and the Rabbit',
        phase=6,
        order=24,
        pages=['A kitten and a rabbit lived on a hilltop.', 'The kitten was quick and playful.', 'The rabbit was calm and clever.', 'One sunset, they went to the pond.', 'An insect buzzed on the water.', 'The kitten tried to catch it but fell in!', 'The rabbit pulled the kitten out.', '"Thank you," said the kitten. "You are a good friend."'],
        comprehension=[('Where did the kitten and rabbit live?', 'On a hilltop.'), ('What happened to the kitten at the pond?', 'The kitten tried to catch an insect but fell in.'), ('Who saved the kitten?', 'The rabbit pulled the kitten out.')],
    ),
    LibraryStory(
        slug='i-can-read',
        title='I Can Read!',
        phase=6,
        order=25,
        pages=['I can read now!', 'I learned all the sounds.', 'I can read about a cat on a mat.', 'I can read about rain and boats.', 'I can read about the moon and stars.', 'Reading is the best thing I can do.', 'I will read every day!'],
        comprehension=[('What can the reader do now?', 'Read!'), ('What kinds of things can they read about?', 'Cats, boats, knights, turtles, and action at a station.'), ('When will the reader read?', 'Every day for the rest of their life.')],
    ),
    LibraryStory(
        slug='the-lamb-and-the-gnat',
        title='The Lamb and the Gnat',
        phase=7,
        order=26,
        pages=['A lamb sat on a hill.', 'A gnat sat on the lamb.', 'The lamb did not like the gnat.', 'The lamb did climb the hill to get rid of the gnat.', 'A ghost came from the fog.', 'The gnat got scared and left.', 'The lamb sat on the hill in the sun.'],
        comprehension=[('Who was sitting on the lamb?', 'A gnat.'), ('What scared the gnat away?', 'A ghost came from the fog.'), ('Where did the lamb end up?', 'On the hill in the sun.')],
    ),
    LibraryStory(
        slug='the-biggest-splash',
        title='The Biggest Splash',
        phase=7,
        order=27,
        pages=['Kim ran to the pond.', 'She made a big splash.', 'Tom made a bigger splash.', '"I will make the biggest splash!" said Jim.', 'Jim ran quickly and did a big jump.', 'Splash! It was the biggest one yet.', 'Kim walked slowly back to try again.', 'She went carefully this time.', 'She made the fastest run and the biggest splash of all!'],
        comprehension=[('Who made the first splash?', 'Kim made the first splash.'), ('Who made the biggest splash?', 'Kim made the biggest splash of all at the end.'), ('How did Jim jump?', 'Jim ran quickly and did a big jump.')],
    ),
    LibraryStory(
        slug='the-little-turtle',
        title='The Little Turtle',
        phase=7,
        order=28,
        pages=['A little turtle sat in a puddle.', 'The puddle was in the middle of the road.', 'A helpful man came along.', 'He picked up the little turtle.', 'He set it on the grass by a table.', 'The turtle ate a simple meal of bugs.', 'The turtle felt the kindness of the man.', 'It was a good day for the little turtle.'],
        comprehension=[('Where was the turtle?', 'In a puddle in the middle of the road.'), ('Who helped the turtle?', 'A helpful man.'), ('What did the turtle eat?', 'A simple meal of bugs.')],
    ),
    LibraryStory(
        slug='the-action-at-the-station',
        title='The Action at the Station',
        phase=7,
        order=29,
        pages=['There was action at the station.', 'A man had to make a decision.', '"Which train do I take?" he said.', 'He had a vision of the sea.', '"I will go to the coast," he said.', 'He got on the train with a motion of his hand.', 'The train left the station.', 'It was the best decision he ever made.'],
        comprehension=[('What decision did the man have to make?', 'Which train to take.'), ('Where did the man decide to go?', 'To the coast.'), ('Was it a good decision?', 'Yes, it was the best decision he ever made.')],
    ),
    LibraryStory(
        slug='i-am-a-reader',
        title='I Am a Reader',
        phase=7,
        order=30,
        pages=['I am a reader.', 'I learned every sound.', 'I can read about a cat on a mat.', 'I can read about a boat on a road.', 'I can read about a knight who could write.', 'I can read about a little turtle in a puddle.', 'I can read about action at a station.', 'Reading is the best thing in the world.', 'I will read every day for the rest of my life.', 'I am a reader!'],
        comprehension=[('What did the reader learn?', 'Every sound.'), ('What is the best thing the reader can do?', 'Reading is the best thing in the world.'), ('Will the reader keep reading?', 'Yes, every day.')],
    ),
]


def stories_by_phase() -> dict[int, list[LibraryStory]]:
    """Decision 0106: every vendored story, grouped by phase and
    sorted by its own `order` within that phase -- the read-only
    "what's in the library" view for Parent Controls. A plain
    accessor, not a selection function (`pick_library_book()` is the
    only thing that reads/writes which story a child actually gets),
    so nothing here ever needs `completed_slugs`."""
    grouped: dict[int, list[LibraryStory]] = {phase_id: [] for phase_id, _title, _subtitle in PHASES}
    for story in _LIBRARY_STORIES:
        grouped.setdefault(story.phase, []).append(story)
    for stories in grouped.values():
        stories.sort(key=lambda s: s.order)
    return grouped


def pick_library_book(
    phase: int, objective: Objective, completed_slugs: set[str],
) -> GeneratedBook | None:
    """Returns the lowest-`order` vendored story at `phase` not
    already in `completed_slugs`, or `None` if every story at that
    phase has already been read (the caller falls through to its
    existing LLM -> hand-written-bank -> word-drill chain). Not
    re-verified against this codebase's own decodability budget --
    see the module docstring for why that's deliberate here, unlike
    story_bank.py's own hand-written stories."""
    candidates = sorted(
        (s for s in _LIBRARY_STORIES if s.phase == phase and s.slug not in completed_slugs),
        key=lambda s: s.order,
    )
    if not candidates:
        return None

    chosen = candidates[0]
    return GeneratedBook(
        title=chosen.title,
        pages=list(chosen.pages),
        target_grapheme=objective.target_grapheme,
        objective=objective,
        sight_words=set(),
        generation_source="story_library",
        library_slug=chosen.slug,
        comprehension=list(chosen.comprehension),
    )
