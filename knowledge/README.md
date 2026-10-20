# ChatQuadra Knowledge Base

Reference material for building the 16 Repliers (Persona Engine) and the user-type estimator (Inference). Everything here is **our own wording**, written from the sources below. Persona prompts and specs are built from these files, so nothing in this folder may be copied text from a copyrighted source.

## Files

| File | What it gives us | Used by |
|---|---|---|
| [01-jung-foundations.md](01-jung-foundations.md) | Jung's original model: attitudes, functions, rational vs irrational, compensation | Everyone, read first |
| [02-cognitive-functions.md](02-cognitive-functions.md) | The 8 functions: what each notices, how it sounds in a chat, healthy vs stressed | Persona Engine, Inference |
| [03-type-dynamics.md](03-type-dynamics.md) | Function stacks, the J/P rule, opposing pairs, the "grip", growth phases | Persona Engine (mood/stress states) |
| [04-nicknames-and-groups.md](04-nicknames-and-groups.md) | Our own type nicknames and group names (no third-party branding) | UI, persona gallery |
| [05-inference-signals.md](05-inference-signals.md) | What in a user's typing points to which preference; how we produce the top-2 result | Inference |
| [types/](types/) | 16 persona-oriented profiles: voice, what they notice, conflict, stress, sample lines, classifier tells | Persona Engine |

## Sources and how we may use them

| Source | Status | How we use it |
|---|---|---|
| C. G. Jung, *Psychological Types*, Ch. X "General Description of the Types", 1923 English trans. by H. Godwin Baynes. Local copy: `sources/jung-1923-psychological-types-ch10/` (from psychclassics.yorku.ca) | Public domain in the US (published 1923). Check before using in other countries. | Short quotes with citation are fine. Main source for the theory. |
| A. J. Drenth, *The 16 Personality Types: Profiles, Theory, & Type Development* (Inquire Books, 2013). Local file: `../16personalities.pdf` | **Copyrighted, all rights reserved.** Not to be committed, redistributed or quoted at length. | Read as reference. Its *ideas* inform our profiles (the functional-stack reading, the inferior-function "grip", three development phases, the J/P rule for introverts), credited where used. No copied passages. |
| 16personalities.com (NERIS Analytics) | Copyrighted content and trademarks | **Not used.** No scraping, no copying of its nicknames, group names, art or test questions. Its model (five letters with Assertive/Turbulent) is also not Jungian, so it doesn't match our function-based approach. |
| MBTI® / Myers-Briggs® | Trademarks of The Myers-Briggs Company | We use the generic four-letter codes and never call our product "MBTI". |

Other well-known works that the ideas here build on, credited by name but not reproduced: Isabel Briggs Myers, *Gifts Differing* (1980); Marie-Louise von Franz, *The Inferior Function* (1971); Naomi Quenk, *Was That Really Me?* (2002, the source of "in the grip"); John Beebe's eight-function archetype model; David Keirsey's temperaments; McCrae & Costa (1989) on MBTI and Big Five correlations.

## Writing rules for this folder
1. Write in our own words. Quote Jung (public domain) sparingly. Never paste text from Drenth or other copyrighted works.
2. Describe **tendencies, not destinies.** Every type file should read as "often" or "tends to", never "always".
3. Keep it **conversational**. The goal is a character who *texts* like this type, not an encyclopedia entry.
4. No stereotypes by gender, culture or nationality. Older sources (Jung included) make gendered claims. We don't carry them forward.
