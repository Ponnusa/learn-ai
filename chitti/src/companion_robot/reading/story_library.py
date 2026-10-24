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
from dataclasses import dataclass, field

from .curriculum import MASTERY_THRESHOLD
from .decodability import clean_word, decompose
from .schema import GeneratedBook, Objective, ReadingProfile

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
    # Decision 0107: the source project's own one-line summary, and
    # each target word tagged with the lesson that introduces it --
    # vendored alongside the story itself, not reinvented, so a
    # parent sees exactly what the source app would show ("what word
    # the child is learning for each story").
    description: str = ""
    words: list[tuple[str, int]] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.pages)


_LIBRARY_STORIES: list[LibraryStory] = [
    LibraryStory(
        slug='sam-sat',
        title='Sam Sat',
        phase=1,
        order=1,
        description='The very first story. Uses only Phase 1 sounds.',
        pages=['Sam sat.', 'Sam sat at the mat.', 'A rat sat at the mat.', 'Sam is mad at the rat.'],
        comprehension=[('Where did Sam sit?', 'Sam sat at the mat.'), ('Who else sat at the mat?', 'A rat sat at the mat.'), ('How did Sam feel about the rat?', 'Sam is mad at the rat.')],
        words=[('a', 3), ('sam', 6), ('at', 7), ('mat', 7), ('sat', 8), ('rat', 9), ('mad', 12), ('is', 15), ('the', 17)],
    ),
    LibraryStory(
        slug='the-cat-at-the-mat',
        title='The Cat at the Mat',
        phase=1,
        order=2,
        description='A cat and a rat at the mat.',
        pages=['The cat is at the mat.', 'The rat is at the mat.', 'The cat is mad.', 'The rat is sad.', 'The cat sat. The rat sat.'],
        comprehension=[('Who sat at the mat first?', 'The cat sat at the mat.'), ('How did the cat feel?', 'The cat is mad.'), ('What did the rat do?', 'The rat rid the mat.')],
        words=[('at', 7), ('mat', 7), ('sat', 8), ('rat', 9), ('mad', 12), ('sad', 12), ('is', 15), ('the', 17), ('cat', 19)],
    ),
    LibraryStory(
        slug='it-is-dim',
        title='It Is Dim',
        phase=1,
        order=3,
        description='Using i, th, and d sounds.',
        pages=['It is dim.', 'Sam sat in the mist.', 'A rat rid this mat.', 'Sam is sad. That is it.'],
        comprehension=[('What was it like?', 'It is dim and there is mist.'), ('Who sat in the mist?', 'Sam sat in the mist.')],
        words=[('a', 3), ('sam', 6), ('mat', 7), ('sat', 8), ('rat', 9), ('sad', 12), ('dim', 15), ('is', 15), ('it', 28), ('mist', 14), ('rid', 14), ('that', 16), ('the', 17), ('this', 16), ('in', 24)],
    ),
    LibraryStory(
        slug='the-man-and-the-dog',
        title='The Man and the Dog',
        phase=2,
        order=4,
        description='A funny story about a naughty dog who loves mud.',
        pages=['A man had a dog.', 'The dog was not a good dog.', 'The dog ran in the mud.', 'The dog dug and dug.', 'The dog got mud on the rug!', '"Not the rug!" the man said.', 'The dog sat on the man.', 'The man got mud on him too!', '"You are fun," the man said. "But you are a mud dog!"'],
        comprehension=[('Was the dog a good dog?', 'No, the dog was not a good dog.'), ('What did the dog get mud on?', 'The dog got mud on the rug.'), ('What did the man call the dog?', 'A mud dog!')],
        words=[('a', 3), ('sat', 8), ('is', 15), ('the', 17), ('man', 23), ('on', 24), ('ran', 23), ('fun', 26), ('mud', 27), ('dog', 22), ('got', 21), ('log', 106), ('had', 39), ('and', 28), ('not', 24), ('rug', 33), ('hug', 39), ('dug', 77)],
    ),
    LibraryStory(
        slug='i-will-not-fall',
        title='I Will Not Fall',
        phase=2,
        order=5,
        description='A story about not giving up.',
        pages=['"I will not fall," I said.', 'I ran to the hill.', 'I got to the hill.', '"I did it!" I said.', 'I sat on the hill.'],
        comprehension=[('Where did the reader run to?', 'To the hill.'), ('Did the reader fall?', 'No, the reader did not fall.')],
        words=[('sat', 8), ('did', 25), ('it', 28), ('the', 17), ('to', 26), ('not', 24), ('on', 24), ('ran', 23), ('fall', 118), ('will', 32), ('got', 21), ('hill', 133), ('i', 34), ('said', 22)],
    ),
    LibraryStory(
        slug='the-fish-in-the-dish',
        title='The Fish in the Dish',
        phase=2,
        order=6,
        description='A fishing story with sh sounds.',
        pages=['The fish is in the dish.', 'A man got the fish.', '"I will shut the lid," the man said.', 'The fish is fun.', 'The man and the fish sat.'],
        comprehension=[('Where is the fish?', 'The fish is in the dish.'), ('What did the man do with the lid?', 'He shut the lid.')],
        words=[('a', 3), ('sat', 8), ('is', 15), ('the', 17), ('in', 24), ('man', 23), ('fun', 26), ('lid', 29), ('will', 32), ('got', 21), ('dish', 35), ('fish', 35), ('shut', 36), ('i', 34), ('said', 22), ('and', 28)],
    ),
    LibraryStory(
        slug='a-hat-for-the-man',
        title='A Hat for the Man',
        phase=2,
        order=7,
        description='A story about a hat.',
        pages=['The man had a hat.', 'The dog got the hat.', 'The man is mad.', 'The dog ran with the hat.', 'The man ran at the dog.', 'The man got his hat.'],
        comprehension=[('Who took the hat?', 'The dog got the hat.'), ('What did the man do?', 'The man ran at the dog to get his hat.'), ('Did the man get the hat back?', 'Yes, the man got his hat.')],
        words=[('a', 3), ('at', 7), ('mad', 12), ('is', 15), ('the', 17), ('man', 23), ('ran', 23), ('with', 40), ('dog', 22), ('got', 21), ('had', 39), ('hat', 39), ('his', 83)],
    ),
    LibraryStory(
        slug='the-red-bed',
        title='The Red Bed',
        phase=3,
        order=8,
        description='A story using short e, b, and other Phase 3 sounds.',
        pages=['Ben had a red bed.', 'The bed is big.', 'His pet bit the bed.', '"Bad pet!" Ben.', 'Ben let his pet on the red bed.'],
        comprehension=[('What color was the bed?', 'The bed was red.'), ('What did the pet do to the bed?', 'The pet bit the bed.'), ('Did Ben let the pet stay on the bed?', 'Yes, Ben let his pet on the red bed.')],
        words=[('a', 3), ('is', 15), ('the', 17), ('on', 24), ('had', 39), ('his', 83), ('let', 52), ('pet', 52), ('red', 52), ('bad', 54), ('bed', 54), ('ben', 100), ('big', 45), ('bit', 54)],
    ),
    LibraryStory(
        slug='the-king-and-the-ring',
        title='The King and the Ring',
        phase=3,
        order=9,
        description='A king loses his ring and the whole kingdom helps look for it.',
        pages=['The king had a big ring.', 'One day the ring fell off his hand.', '"My ring! My ring is gone!" the king said.', 'The king told his men to look for it.', 'The men did look and look.', 'One man found the ring in the mud.', '"I got it!" the man said.', 'The king put the ring on his hand.', 'He was so glad he did sing a song.', 'All the men did sing with the king.'],
        comprehension=[('What did the king lose?', 'The king lost his big ring.'), ('Where was the ring found?', 'The ring was found in the mud.'), ('What did the king do when he got the ring back?', 'He sang a song.')],
        words=[('a', 3), ('is', 15), ('the', 17), ('not', 24), ('on', 24), ('look', 94), ('had', 39), ('his', 83), ('men', 52), ('big', 45), ('king', 56), ('ring', 56), ('sing', 56), ('my', 72)],
    ),
    LibraryStory(
        slug='the-jar',
        title='The Jar of Jam',
        phase=3,
        order=10,
        description='Jim wants jam but the jar is too far up! A funny story about reaching high.',
        pages=['Jim had a jar of jam.', 'But the jar was up far too high!', 'Jim got on a big box.', 'He got on his tip toes.', 'He got the jar!', 'But then — he fell off the box!', 'The jar of jam fell too.', 'Jam got on Jim. Jam got on the rug.', 'Jam got on the cat!', '"Yum!" said Jim. He ate the jam off his hand.', 'The cat ate the jam off the rug.'],
        comprehension=[('What did Jim want?', 'Jim wanted the jar of jam.'), ('What happened when Jim fell?', 'Jam got on Jim, the rug, and the cat.'), ('Who ate the jam off the rug?', 'The cat ate the jam off the rug.')],
        words=[('a', 3), ('is', 15), ('the', 17), ('on', 24), ('not', 24), ('got', 21), ('had', 39), ('his', 83), ('put', 48), ('far', 49), ('up', 100), ('yum', 100), ('jam', 67), ('jar', 67), ('jim', 100)],
    ),
    LibraryStory(
        slug='my-pet',
        title='My Pet',
        phase=3,
        order=11,
        description='A story using ȳ, er, oo, and Phase 3 sounds.',
        pages=['My pet is a cat.', 'Her name is Moon.', 'Moon is fun.', 'Moon can run and run.', 'Moon sits on my bed at the end of the day.', 'I love my pet Moon.'],
        comprehension=[('What is the pet?', 'The pet is a cat named Moon.'), ('What can Moon do?', 'Moon can run and run.'), ('Where does Moon sit at the end of the day?', 'Moon sits on the bed.')],
        words=[('a', 3), ('at', 7), ('is', 15), ('sits', 14), ('the', 17), ('cat', 19), ('can', 24), ('on', 24), ('of', 94), ('fun', 26), ('run', 28), ('name', 37), ('love', 45), ('pet', 52), ('bed', 54), ('i', 34), ('day', 84), ('her', 62), ('moon', 65), ('my', 72), ('and', 28), ('end', 100)],
    ),
    LibraryStory(
        slug='when-i-ride',
        title='When I Ride',
        phase=3,
        order=12,
        description='A story using wh, ī, ȳ sounds.',
        pages=['When I ride my bike, I go far.', 'I ride by the park.', 'I ride by the shop.', 'I ride and ride until it is time to go.', 'Riding is fun.'],
        comprehension=[('What does the reader ride?', 'A bike.'), ('Where does the reader ride by?', 'By the park and by the shop.'), ('Is riding fun?', 'Yes, riding is fun.')],
        words=[('is', 15), ('it', 28), ('the', 17), ('to', 26), ('fun', 26), ('until', 123), ('go', 44), ('shop', 100), ('far', 49), ('park', 49), ('riding', 100), ('bike', 58), ('i', 34), ('ride', 59), ('time', 59), ('when', 69), ('by', 124), ('my', 72), ('and', 28)],
    ),
    LibraryStory(
        slug='the-rain',
        title='The Rain',
        phase=4,
        order=13,
        description='A story using ai words.',
        pages=['The rain came.', 'I read a book on my seat.', 'My pal ate a meal.', 'We waited for the rain to end.', 'The sun came. We ran to the tail of the road.', 'We had a real good time.'],
        comprehension=[('What happened when it rained?', 'The reader read a book on a seat.'), ('What did the reader do when the rain stopped?', 'Ran to the tail of the road.')],
        words=[('a', 3), ('seat', 91), ('the', 17), ('road', 82), ('to', 26), ('on', 24), ('ran', 23), ('for', 68), ('of', 94), ('sun', 98), ('ate', 92), ('came', 90), ('had', 39), ('pal', 100), ('we', 94), ('i', 34), ('time', 59), ('book', 97), ('good', 81), ('my', 72), ('meal', 79), ('read', 79), ('real', 144), ('rain', 88), ('tail', 88), ('waited', 100), ('end', 100)],
    ),
    LibraryStory(
        slug='the-team',
        title='The Team',
        phase=4,
        order=14,
        description='A story about a team using ea words.',
        pages=['Dean and Jean are a team.', 'Dean can read and read.', 'Jean can leap far.', 'One day the rain came.', '"Wait!" said Dean. "I can read to you."', 'So Dean read a tale to Jean.', 'Jean said, "That was the best tale!"', 'A good team can do a lot.'],
        comprehension=[('What can Dean do?', 'Dean can read and read.'), ('What can Jean do?', 'Jean can leap far.'), ('What did the team do in the rain?', 'The team had to wait.')],
        words=[('a', 3), ('team', 79), ('is', 15), ('the', 17), ('do', 26), ('can', 24), ('far', 49), ('dean', 79), ('lean', 79), ('leap', 79), ('read', 79), ('meat', 79), ('meal', 79), ('rain', 88), ('wait', 88)],
    ),
    LibraryStory(
        slug='mail-for-me',
        title='Mail for Me',
        phase=4,
        order=15,
        description='A story using ai and ea words.',
        pages=['The mail came at noon.', '"Is the mail for me?"', 'A letter had my name on it.', 'I read the letter.', '"Dear pal, I aim to see you," it said.', 'I sat to read it all.'],
        comprehension=[('What came at noon?', 'The mail came at noon.'), ('Who was the letter from?', 'The letter was from a pal.'), ('What did the letter say?', 'Dear pal, I aim to see you.')],
        words=[('a', 3), ('me', 141), ('see', 80), ('at', 7), ('sat', 8), ('dear', 12), ('is', 15), ('it', 28), ('the', 17), ('to', 26), ('on', 24), ('for', 68), ('all', 118), ('came', 90), ('name', 37), ('had', 39), ('pal', 100), ('i', 34), ('letter', 150), ('noon', 65), ('my', 72), ('read', 79), ('aim', 88), ('mail', 88), ('said', 22), ('you', 30)],
    ),
    LibraryStory(
        slug='the-loud-sound',
        title='The Loud Hound',
        phase=5,
        order=16,
        description='A noisy hound causes chaos — and catches a mouse!',
        pages=['I heard a loud sound.', 'I looked out the door.', 'A big hound was running round and round the yard!', 'He ran so fast his ears went up and out.', 'Then he stopped. He put his nose on the ground.', 'He found something! A mouse!', 'The mouse ran. The hound ran.', 'The mouse hid. The hound could not find it.', 'The hound sat down and let out a loud howl.', 'I think the mouse won.'],
        comprehension=[('What was making the loud sound?', 'A big hound was running round and round.'), ('What did the hound find?', 'The hound found a mouse.'), ('Who won — the hound or the mouse?', 'The mouse won because the hound could not find it.')],
        words=[('a', 3), ('is', 15), ('the', 17), ('on', 24), ('not', 24), ('ran', 23), ('big', 45), ('i', 34), ('door', 65), ('looked', 98), ('found', 96), ('hound', 112), ('loud', 89), ('mouse', 89), ('out', 89), ('round', 89), ('sound', 90), ('ground', 94)],
    ),
    LibraryStory(
        slug='out-and-about',
        title='Out and About',
        phase=5,
        order=17,
        description='A fluency story using ou words.',
        pages=['I went out of the house.', 'I found a round rock on the ground.', 'I shouted, "Look at this!"', 'My pal came running out.', 'We counted the rocks we had found.', 'We found four round rocks in all.'],
        comprehension=[('What did the reader find on the ground?', 'A round rock.'), ('How many round rocks did they find?', 'Four round rocks.')],
        words=[('a', 3), ('at', 7), ('the', 17), ('this', 16), ('in', 24), ('on', 24), ('of', 94), ('all', 118), ('came', 90), ('had', 39), ('rock', 124), ('rocks', 100), ('pal', 100), ('we', 94), ('went', 68), ('running', 100), ('i', 34), ('look', 94), ('my', 72), ('counted', 100), ('found', 96), ('four', 89), ('house', 89), ('out', 89), ('round', 89), ('shouted', 100), ('ground', 94)],
    ),
    LibraryStory(
        slug='the-frog-and-the-crab',
        title='The Frog and the Crab',
        phase=6,
        order=18,
        description='A story using consonant blends.',
        pages=['A frog sat on a flat rock.', 'A crab crept from the creek.', '"What are you doing?" said the frog.', '"I am looking for a snack," said the crab.', 'The frog did a big flip into the stream.', 'Splash! The crab got wet.', '"Do it again!" said the crab.'],
        comprehension=[('What was the crab looking for?', 'The crab was looking for a snack.'), ('What did the frog do?', 'The frog did a big flip into the stream.'), ('Did the crab want the frog to do it again?', 'Yes! The crab said "Do it again!"')],
        words=[('a', 3), ('am', 4), ('sat', 8), ('did', 25), ('it', 28), ('the', 17), ('do', 26), ('into', 100), ('on', 24), ('for', 68), ('got', 21), ('rock', 124), ('are', 125), ('wet', 31), ('big', 45), ('doing', 100), ('i', 34), ('looking', 100), ('what', 70), ('again', 98), ('said', 22), ('you', 30), ('flat', 102), ('flip', 102), ('crab', 103), ('creek', 100), ('crept', 106), ('frog', 104), ('from', 90), ('splash', 124), ('stream', 100), ('snack', 100)],
    ),
    LibraryStory(
        slug='a-bright-night',
        title='A Bright Night',
        phase=6,
        order=19,
        description='A story using igh and blend sounds.',
        pages=['The night was bright with stars.', 'I could see the light from the moon.', '"What a sight!" I said.', 'A flight of birds went past.', 'I sat on the grass and watched the sky.', 'The night was still and right for dreaming.'],
        comprehension=[('What made the night bright?', 'Stars and the light from the moon.'), ('What went past in the sky?', 'A flight of birds.'), ('What was the night good for?', 'Dreaming.')],
        words=[('a', 3), ('see', 80), ('sat', 8), ('the', 17), ('on', 24), ('for', 68), ('of', 94), ('was', 30), ('with', 40), ('past', 110), ('watched', 100), ('went', 68), ('birds', 139), ('i', 34), ('moon', 65), ('what', 70), ('sky', 71), ('said', 22), ('could', 100), ('dreaming', 100), ('from', 90), ('grass', 134), ('stars', 100), ('still', 108), ('and', 28), ('bright', 120), ('flight', 120), ('light', 120), ('night', 120), ('right', 120), ('sight', 120)],
    ),
    LibraryStory(
        slug='the-snowman',
        title='The Snowman',
        phase=6,
        order=20,
        description='A story using ow and ew sounds.',
        pages=['The snow fell slow and soft.', 'I knew it was time to go out.', 'I threw on my coat and gloves.', 'I made a snowman in the yard.', 'He had a brown hat and a long scarf.', 'A few crows sat on his arms.', '"I know you will melt," I said, "but for now, you are my friend."'],
        comprehension=[('What did the reader make?', 'A snowman in the yard.'), ('What sat on the snowman?', 'A few crows sat on his arms.'), ('Will the snowman last forever?', 'No, the reader knows he will melt.')],
        words=[('a', 3), ('sat', 8), ('it', 28), ('the', 17), ('coat', 82), ('to', 26), ('in', 24), ('on', 24), ('for', 68), ('was', 30), ('will', 32), ('made', 141), ('had', 39), ('hat', 39), ('he', 39), ('his', 83), ('go', 44), ('arms', 100), ('are', 125), ('fell', 88), ('gloves', 100), ('but', 98), ('long', 112), ('i', 34), ('time', 59), ('yard', 60), ('my', 72), ('said', 22), ('out', 89), ('you', 30), ('slow', 116), ('snow', 115), ('scarf', 100), ('and', 28), ('friend', 112), ('melt', 113), ('soft', 113), ('brown', 115), ('crows', 100), ('now', 115), ('snowman', 100), ('knew', 124), ('know', 116), ('few', 122), ('threw', 122)],
    ),
    LibraryStory(
        slug='joy-and-the-toy',
        title='Joy and the Toy',
        phase=6,
        order=21,
        description='A story using oi/oy sounds.',
        pages=['Joy went to the toy shop.', 'She saw coins and trains and dolls.', '"Which toy do you enjoy the most?" said Mom.', 'Joy pointed at a small drum.', '"That one!" she said with a smile.', 'She joined the line to pay.', 'Joy played her drum all the way home.'],
        comprehension=[('Where did Joy go?', 'Joy went to the toy shop.'), ('What toy did Joy pick?', 'Joy pointed at a small drum.'), ('What did Joy do on the way home?', 'Joy played her drum all the way home.')],
        words=[('a', 3), ('at', 7), ('that', 16), ('the', 17), ('do', 26), ('mom', 21), ('most', 21), ('to', 26), ('coins', 100), ('all', 118), ('dolls', 29), ('with', 40), ('she', 35), ('home', 86), ('shop', 100), ('one', 100), ('pointed', 100), ('went', 68), ('line', 58), ('pay', 60), ('way', 84), ('her', 62), ('enjoy', 100), ('joined', 100), ('which', 69), ('said', 22), ('you', 30), ('drum', 104), ('trains', 100), ('small', 124), ('smile', 109), ('played', 111), ('and', 28), ('joy', 117), ('toy', 117), ('saw', 118)],
    ),
    LibraryStory(
        slug='the-knight',
        title='The Knight',
        phase=6,
        order=22,
        description='A story using kn and wr sounds.',
        pages=['The knight could write.', 'He wrote on a scroll with a quill.', 'He knew all the words in the land.', "One day he knocked on the king's door.", '"I have written you a letter," said the knight.', 'The king read the letter and smiled.', '"Kneel and I will make you my scribe."'],
        comprehension=[('What could the knight do?', 'The knight could write.'), ('What did the knight write for the king?', 'A letter.'), ('What did the king make the knight?', 'The king made him his scribe.')],
        words=[('s', 1), ('a', 3), ('the', 17), ('in', 24), ('on', 24), ('all', 118), ('will', 32), ('with', 40), ('words', 125), ('he', 39), ('have', 46), ('make', 52), ('one', 100), ('king', 56), ('i', 34), ('day', 84), ('letter', 150), ('door', 65), ('my', 72), ('quill', 74), ('read', 79), ('said', 22), ('could', 100), ('you', 30), ('smiled', 100), ('scribe', 111), ('scroll', 100), ('and', 28), ('land', 102), ('knight', 125), ('kneel', 121), ('knew', 124), ('knocked', 100), ('write', 121), ('written', 100), ('wrote', 121)],
    ),
    LibraryStory(
        slug='the-straw-hat',
        title='The Straw Hat',
        phase=6,
        order=23,
        description='A story using aw sounds and blends.',
        pages=['I saw a straw hat on the wall.', 'I put it on and walked outside.', 'The sun was hot and the sky was bright.', 'I drew a picture on the path with chalk.', 'A small hawk flew past.', 'I sat in the shade and yawned.', 'The straw hat kept the sun off my face.'],
        comprehension=[('What did the reader find on the wall?', 'A straw hat.'), ('What did the reader draw?', 'A picture on the path with chalk.'), ('What flew past?', 'A small hawk.')],
        words=[('a', 3), ('sat', 8), ('it', 28), ('the', 17), ('in', 24), ('on', 24), ('off', 124), ('sun', 98), ('wall', 118), ('was', 30), ('with', 40), ('face', 37), ('shade', 37), ('hat', 39), ('hot', 39), ('hawk', 100), ('past', 110), ('path', 48), ('put', 48), ('chalk', 100), ('kept', 100), ('picture', 52), ('walked', 148), ('i', 34), ('yawned', 100), ('my', 72), ('sky', 71), ('outside', 89), ('small', 124), ('and', 28), ('saw', 118), ('straw', 118), ('bright', 120), ('drew', 122), ('flew', 122)],
    ),
    LibraryStory(
        slug='the-kitten-and-the-rabbit',
        title='The Kitten and the Rabbit',
        phase=6,
        order=24,
        description='A story using multi-syllable words.',
        pages=['A kitten and a rabbit lived on a hilltop.', 'The kitten was quick and playful.', 'The rabbit was calm and clever.', 'One sunset, they went to the pond.', 'An insect buzzed on the water.', 'The kitten tried to catch it but fell in!', 'The rabbit pulled the kitten out.', '"Thank you," said the kitten. "You are a good friend."'],
        comprehension=[('Where did the kitten and rabbit live?', 'On a hilltop.'), ('What happened to the kitten at the pond?', 'The kitten tried to catch an insect but fell in.'), ('Who saved the kitten?', 'The rabbit pulled the kitten out.')],
        words=[('a', 3), ('it', 28), ('the', 17), ('to', 26), ('an', 144), ('in', 24), ('on', 24), ('calm', 29), ('was', 30), ('hilltop', 48), ('catch', 141), ('are', 125), ('fell', 88), ('insect', 123), ('kitten', 123), ('lived', 100), ('one', 100), ('pulled', 52), ('sunset', 123), ('went', 68), ('but', 98), ('rabbit', 123), ('they', 134), ('water', 94), ('good', 81), ('quick', 74), ('buzzed', 75), ('said', 22), ('out', 89), ('you', 30), ('clever', 100), ('tried', 107), ('playful', 111), ('and', 28), ('friend', 112), ('pond', 106), ('thank', 112)],
    ),
    LibraryStory(
        slug='i-can-read',
        title='I Can Read!',
        phase=6,
        order=25,
        description='A graduation story celebrating reading.',
        pages=['I can read now!', 'I learned all the sounds.', 'I can read about a cat on a mat.', 'I can read about rain and boats.', 'I can read about the moon and stars.', 'Reading is the best thing I can do.', 'I will read every day!'],
        comprehension=[('What can the reader do now?', 'Read!'), ('What kinds of things can they read about?', 'Cats, boats, knights, turtles, and action at a station.'), ('When will the reader read?', 'Every day for the rest of their life.')],
        words=[('a', 3), ('mat', 7), ('is', 15), ('the', 17), ('cat', 19), ('do', 26), ('can', 24), ('on', 24), ('all', 118), ('will', 32), ('best', 94), ('boats', 100), ('thing', 57), ('i', 34), ('day', 84), ('every', 125), ('moon', 65), ('learned', 125), ('read', 79), ('reading', 125), ('rain', 88), ('about', 89), ('sounds', 125), ('stars', 100), ('and', 28), ('now', 115)],
    ),
    LibraryStory(
        slug='the-lamb-and-the-gnat',
        title='The Lamb and the Gnat',
        phase=7,
        order=26,
        description='A story using silent letter patterns gn, mb, and gh.',
        pages=['A lamb sat on a hill.', 'A gnat sat on the lamb.', 'The lamb did not like the gnat.', 'The lamb did climb the hill to get rid of the gnat.', 'A ghost came from the fog.', 'The gnat got scared and left.', 'The lamb sat on the hill in the sun.'],
        comprehension=[('Who was sitting on the lamb?', 'A gnat.'), ('What scared the gnat away?', 'A ghost came from the fog.'), ('Where did the lamb end up?', 'On the hill in the sun.')],
        words=[('lamb', 129), ('gnat', 129), ('climb', 129), ('ghost', 130), ('sat', 8), ('hill', 133), ('the', 17), ('on', 24), ('a', 3)],
    ),
    LibraryStory(
        slug='the-biggest-splash',
        title='The Biggest Splash',
        phase=7,
        order=27,
        description='A story using comparative suffixes -er, -est, -ly.',
        pages=['Kim ran to the pond.', 'She made a big splash.', 'Tom made a bigger splash.', '"I will make the biggest splash!" said Jim.', 'Jim ran quickly and did a big jump.', 'Splash! It was the biggest one yet.', 'Kim walked slowly back to try again.', 'She went carefully this time.', 'She made the fastest run and the biggest splash of all!'],
        comprehension=[('Who made the first splash?', 'Kim made the first splash.'), ('Who made the biggest splash?', 'Kim made the biggest splash of all at the end.'), ('How did Jim jump?', 'Jim ran quickly and did a big jump.')],
        words=[('bigger', 135), ('biggest', 135), ('faster', 135), ('fastest', 124), ('quickly', 136), ('slowly', 136), ('carefully', 148), ('splash', 124), ('pond', 106)],
    ),
    LibraryStory(
        slug='the-little-turtle',
        title='The Little Turtle',
        phase=7,
        order=28,
        description='A story using consonant-le syllables and suffixes.',
        pages=['A little turtle sat in a puddle.', 'The puddle was in the middle of the road.', 'A helpful man came along.', 'He picked up the little turtle.', 'He set it on the grass by a table.', 'The turtle ate a simple meal of bugs.', 'The turtle felt the kindness of the man.', 'It was a good day for the little turtle.'],
        comprehension=[('Where was the turtle?', 'In a puddle in the middle of the road.'), ('Who helped the turtle?', 'A helpful man.'), ('What did the turtle eat?', 'A simple meal of bugs.')],
        words=[('little', 100), ('turtle', 142), ('puddle', 142), ('middle', 142), ('table', 142), ('apple', 143), ('simple', 143), ('kindness', 138), ('helpful', 137)],
    ),
    LibraryStory(
        slug='the-action-at-the-station',
        title='The Action at the Station',
        phase=7,
        order=29,
        description='A story using -tion and -sion suffixes.',
        pages=['There was action at the station.', 'A man had to make a decision.', '"Which train do I take?" he said.', 'He had a vision of the sea.', '"I will go to the coast," he said.', 'He got on the train with a motion of his hand.', 'The train left the station.', 'It was the best decision he ever made.'],
        comprehension=[('What decision did the man have to make?', 'Which train to take.'), ('Where did the man decide to go?', 'To the coast.'), ('Was it a good decision?', 'Yes, it was the best decision he ever made.')],
        words=[('action', 140), ('station', 140), ('nation', 140), ('fiction', 140), ('vision', 140), ('decision', 140), ('motion', 140)],
    ),
    LibraryStory(
        slug='i-am-a-reader',
        title='I Am a Reader',
        phase=7,
        order=30,
        description='The final graduation story celebrating all sounds learned.',
        pages=['I am a reader.', 'I learned every sound.', 'I can read about a cat on a mat.', 'I can read about a boat on a road.', 'I can read about a knight who could write.', 'I can read about a little turtle in a puddle.', 'I can read about action at a station.', 'Reading is the best thing in the world.', 'I will read every day for the rest of my life.', 'I am a reader!'],
        comprehension=[('What did the reader learn?', 'Every sound.'), ('What is the best thing the reader can do?', 'Reading is the best thing in the world.'), ('Will the reader keep reading?', 'Yes, every day.')],
        words=[('reader', 125), ('every', 125), ('learned', 125), ('sounds', 125), ('reading', 125), ('words', 125), ('world', 141)],
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


def get_story(slug: str) -> LibraryStory | None:
    """Decision 0107: looks up one vendored story by its own slug,
    for the story detail page. A linear scan over 30 entries needs
    no index at this size."""
    for story in _LIBRARY_STORIES:
        if story.slug == slug:
            return story
    return None


# Decision 0107: same convention voice_loop_demo.py's own decision
# 0103 _weakest_mastery_for_miscues() already established for "how
# ready is this text for this child" -- a grapheme never tracked at
# all counts as 0.0 (never observed is at least as strong a reason
# to call a story not-yet-ready as any tracked-but-weak grapheme),
# not skipped. Bucketed into a simple traffic light a parent can
# read at a glance, not the raw probability.
_MASTERY_COLOR_RED_BELOW = 0.5


def mastery_color_for_story(story: LibraryStory, profile: ReadingProfile) -> str:
    """'green' | 'yellow' | 'red' -- the weakest tracked grapheme
    mastery among every word in the story. Deliberately only three
    buckets, no separate "never attempted" state -- a story the
    child hasn't read yet shows the same as "weak" (red), same
    minimal-first-version reasoning as decision 0103's own tiered
    correction budget."""
    weakest = 1.0
    for word in story.text.split():
        cleaned = clean_word(word)
        if not cleaned:
            continue
        for grapheme in decompose(cleaned).graphemes:
            mastery = profile.masteries.get(grapheme.grapheme)
            weakest = min(weakest, mastery.p_mastery if mastery is not None else 0.0)
    if weakest >= MASTERY_THRESHOLD:
        return "green"
    if weakest >= _MASTERY_COLOR_RED_BELOW:
        return "yellow"
    return "red"


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
