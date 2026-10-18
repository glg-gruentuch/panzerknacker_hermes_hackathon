import type {
  Alignment,
  BritannicaPage,
  ChatResponse,
  CoverageRow,
  MatchInfo,
  TopicSummary,
  WikipediaArticle,
  WikipediaCandidate,
} from '../types'

// MOCK DATA. The Britannica passages are written in period style for the demo;
// they are not OCR from the dataset. The Wikipedia passages paraphrase the
// articles' content. Replace both by running the backend (VITE_API_MODE=live).

export interface MockTopic {
  summary: TopicSummary
  aliases: string[]
  britannica: BritannicaPage
  wikipedia: WikipediaArticle | null
  match: MatchInfo
  candidates: WikipediaCandidate[]
  alignments: Alignment[]
  coverage: CoverageRow[]
  suggestedQuestions: string[]
  answers: Record<string, Omit<ChatResponse, 'trace'>>
}

const wiki = (title: string) => `https://en.wikipedia.org/wiki/${title.replace(/ /g, '_')}`

const cite = (...ids: string[]): ChatResponse['citations'] =>
  ids.map((id, i) => ({
    id,
    source: id.startsWith('B') ? 'britannica' : 'wikipedia',
    passageId: id,
    rerankScore: Math.round((0.94 - i * 0.04) * 100) / 100,
  }))

const blood: MockTopic = {
  summary: {
    slug: 'blood',
    label: 'Blood',
    headword: 'BLOOD',
    edition: 'Third edition',
    year: 1797,
    match: 'strong',
    wikipediaTitle: 'Blood',
  },
  aliases: ['blood', 'sanguis', 'circulation of the blood'],
  britannica: {
    pageId: 'MOCK-0001',
    headword: 'BLOOD',
    edition: 'Third edition',
    year: 1797,
    volume: 'Volume 3',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, and miscellaneous literature - Third edition, Volume 3 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `BLO                    [ 302 ]                    BLO

were it not that the ſeeds are often deſtroyed by the
birds. See Botany, Index.
  BLOOD, in anatomy, a red fluid, which circulates
through the arteries and veins of animals, and is the
immediate nouriſhment of every part of the body.
  When drawn from a vein and ſuffered to reſt, it ſe-
parates into two parts: a red maſs called the craſſa-
mentum, or cake, and a thin yellowiſh liquor named the
ſerum. The redneſs is owing to an infinite number of
minute red globules, firſt diſcovered by the micro-
ſcope of Leeuwenhoeck, which ſwim in the ſerum and
are thought to be compreſſible.
  The blood is made from the chyle, which, being pre-
pared from the aliment in the ſtomach and inteſtines,
is conveyed by the lacteal vefſels into the thoracic
duct, and thence into the ſubclavian vein. Its motion
was firſt demonſtrated by our countryman Dr Harvey,
who ſhewed that the heart, by its contraction, drives
the blood through the arteries to every part, from
whence it returns by the veins.
  Of the heat of the blood authors are not agreed;
ſome aſcribing it to a fermentation, others to the fric-
tion of its parts againſt the ſides of the veſſels.
  The ancients reckoned the blood one of the four
humours, and aſcribed to its abundance the ſanguine
temperament. Phyſicians at this day relieve a ple-
thora, or too great fulneſs of blood, by opening a vein.
  TRANSFUSION of blood from one animal into another
was attempted in the laſt century both in England and
France; but the experiments, having ſometimes proved
fatal, were forbidden by authority.
  BLOOD-HOUND, a ſpecies of dog, remarkable for the
acuteneſs of its ſmell. See Canis.`,
    passages: [
      { id: 'B1', section: 'BLOOD', text: 'BLOOD, in anatomy, a red fluid, which circulates through the arteries and veins of animals, and is the immediate nourishment of every part of the body.' },
      { id: 'B2', section: 'BLOOD', text: 'When drawn from a vein and suffered to rest, it separates into two parts: a red mass called the crassamentum, or cake, and a thin yellowish liquor named the serum.' },
      { id: 'B3', section: 'BLOOD', text: 'The redness is owing to an infinite number of minute red globules, first discovered by the microscope of Leeuwenhoek, which swim in the serum and are thought to be compressible.' },
      { id: 'B4', section: 'BLOOD', text: 'The blood is made from the chyle, which, being prepared from the aliment in the stomach and intestines, is conveyed by the lacteal vessels into the thoracic duct, and thence into the subclavian vein.' },
      { id: 'B5', section: 'BLOOD', text: 'Its motion was first demonstrated by our countryman Dr Harvey, who shewed that the heart, by its contraction, drives the blood through the arteries to every part, from whence it returns by the veins.' },
      { id: 'B6', section: 'BLOOD', text: 'Of the heat of the blood authors are not agreed; some ascribing it to a fermentation, others to the friction of its parts against the sides of the vessels.' },
      { id: 'B7', section: 'BLOOD', text: 'The ancients reckoned the blood one of the four humours, and ascribed to its abundance the sanguine temperament. Physicians at this day relieve a plethora, or too great fulness of blood, by opening a vein.' },
      { id: 'B8', section: 'TRANSFUSION', text: 'The transfusion of blood from one animal into another was attempted in the last century both in England and France; but the experiments, having sometimes proved fatal, were forbidden by authority.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-blood',
    title: 'Blood',
    url: wiki('Blood'),
    dateModified: '2026-09-30',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Blood is a body fluid that delivers oxygen and nutrients to the cells and carries metabolic waste away from them. In vertebrates it is made up of blood cells suspended in plasma.' },
      { id: 'W2', section: 'Composition', text: 'Plasma makes up about 55% of blood volume. It is mostly water and carries dissolved proteins, glucose, mineral ions, hormones and carbon dioxide. The rest is red blood cells (erythrocytes), white blood cells (leukocytes) and platelets.' },
      { id: 'W3', section: 'Red blood cells', text: 'Red blood cells contain haemoglobin, an iron-containing protein that binds oxygen in the lungs and releases it in the tissues. Haemoglobin gives blood its red colour.' },
      { id: 'W4', section: 'Production', text: 'Blood cells are produced in the bone marrow, a process called haematopoiesis. Red blood cells circulate for about 120 days before the spleen and liver remove them.' },
      { id: 'W5', section: 'Circulation', text: 'The heart pumps blood around a closed system of arteries, capillaries and veins. The pulmonary circuit carries blood through the lungs, where it picks up oxygen; the systemic circuit carries it to the rest of the body.' },
      { id: 'W6', section: 'Clotting', text: 'When a vessel is injured, platelets and clotting factors form a clot. Strands of fibrin trap red cells into a solid mass, and the clear fluid left behind is called serum.' },
      { id: 'W7', section: 'Body temperature', text: 'Heat is produced mainly by metabolism in the liver and muscles. Blood carries that heat around the body and helps keep its temperature stable.' },
      { id: 'W8', section: 'Transfusion', text: "Blood transfusion became routine after Karl Landsteiner discovered the ABO blood groups in 1901. Matching the donor's group to the recipient's prevents fatal reactions." },
      { id: 'W9', section: 'History', text: 'Bloodletting, justified by the theory of the four humours, was common until the late 19th century. Today it is used only for a few conditions, such as haemochromatosis and polycythaemia.' },
      { id: 'W10', section: 'Disorders', text: 'Disorders of the blood include anaemia, haemophilia, leukaemia and sickle cell disease.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.86,
    rerankScore: 0.93,
    reasons: [
      'Same headword: BLOOD and Blood.',
      'Eight of the ten Wikipedia sections have a counterpart passage on the Britannica page.',
      'The reranker puts it well ahead of the next candidate, Blood plasma (0.61).',
    ],
  },
  candidates: [
    { title: 'Blood plasma', url: wiki('Blood plasma'), embedScore: 0.79, rerankScore: 0.61 },
    { title: 'Circulatory system', url: wiki('Circulatory system'), embedScore: 0.74, rerankScore: 0.55 },
    { title: 'Bloodletting', url: wiki('Bloodletting'), embedScore: 0.7, rerankScore: 0.48 },
  ],
  alignments: [
    { id: 'a1', kind: 'retained', verdict: 'correct', label: 'Blood circulates', britannica: { passageId: 'B1', quote: 'circulates through the arteries and veins' }, wikipedia: { passageId: 'W5', quote: 'a closed system of arteries, capillaries and veins' }, note: 'Both describe the same circuit. Wikipedia also names the capillaries that join arteries to veins.' },
    { id: 'a2', kind: 'retained', verdict: 'correct', label: 'The heart drives it', britannica: { passageId: 'B5', quote: 'the heart, by its contraction, drives the blood through the arteries' }, wikipedia: { passageId: 'W5', quote: 'The heart pumps blood' }, note: "Harvey's account from 1628 still stands; only the wording is plainer." },
    { id: 'a3', kind: 'reworded', verdict: 'correct', label: 'Red globules', britannica: { passageId: 'B3', quote: 'minute red globules' }, wikipedia: { passageId: 'W2', quote: 'red blood cells (erythrocytes)' }, note: 'The same objects. "Globules" was the microscope-era name; they became "cells" once cell theory arrived in the 1830s.' },
    { id: 'a4', kind: 'reworded', verdict: 'correct', label: 'The clot', britannica: { passageId: 'B2', quote: 'a red mass called the crassamentum, or cake' }, wikipedia: { passageId: 'W6', quote: 'form a clot' }, note: 'Crassamentum is Latin for "thickening". The observation is unchanged; the word has gone.' },
    { id: 'a5', kind: 'retained', verdict: 'correct', label: 'Serum', britannica: { passageId: 'B2', quote: 'a thin yellowish liquor named the serum' }, wikipedia: { passageId: 'W6', quote: 'the clear fluid left behind is called serum' }, note: 'Same word, same meaning, in both texts.' },
    { id: 'a6', kind: 'revised', verdict: 'wrong', label: 'Where blood is made', britannica: { passageId: 'B4', quote: 'The blood is made from the chyle' }, wikipedia: { passageId: 'W4', quote: 'Blood cells are produced in the bone marrow' }, note: 'In 1797, blood is made from digested food. Today, food supplies the plasma, but the cells come from the bone marrow.' },
    { id: 'a7', kind: 'revised', verdict: 'wrong', label: 'Why blood is warm', britannica: { passageId: 'B6', quote: 'some ascribing it to a fermentation, others to the friction of its parts' }, wikipedia: { passageId: 'W7', quote: 'Heat is produced mainly by metabolism in the liver and muscles' }, note: 'Neither 1797 theory survived. Heat comes from the tissues; blood only carries it.' },
    { id: 'a8', kind: 'revised', verdict: 'wrong', label: 'Bloodletting', britannica: { passageId: 'B7', quote: 'relieve a plethora, or too great fulness of blood, by opening a vein' }, wikipedia: { passageId: 'W9', quote: 'Today it is used only for a few conditions' }, note: 'Routine treatment in 1797. Now kept for a few disorders where the body holds too much iron or too many red cells.' },
    { id: 'a9', kind: 'revised', verdict: 'partly', label: 'Transfusion', britannica: { passageId: 'B8', quote: 'having sometimes proved fatal, were forbidden by authority' }, wikipedia: { passageId: 'W8', quote: 'Karl Landsteiner discovered the ABO blood groups in 1901' }, note: 'Right that it was dangerous, wrong about why: the deaths came from mismatched blood groups.' },
    { id: 'a10', kind: 'dropped', verdict: 'wrong', label: 'Blood and temperament', britannica: { passageId: 'B7', quote: 'ascribed to its abundance the sanguine temperament' }, wikipedia: null, note: 'The idea that blood shapes character has left medicine entirely.' },
    { id: 'a11', kind: 'added', verdict: null, label: 'Carrying oxygen', britannica: null, wikipedia: { passageId: 'W3', quote: 'binds oxygen in the lungs and releases it in the tissues' }, note: 'The 1797 entry never says what blood carries. Oxygen transport by haemoglobin is entirely new.' },
    { id: 'a12', kind: 'added', verdict: null, label: 'Blood disorders', britannica: null, wikipedia: { passageId: 'W10', quote: 'anaemia, haemophilia, leukaemia and sickle cell disease' }, note: 'None of these is named on the 1797 page.' },
  ],
  coverage: [
    { topic: 'Composition', britannica: 0.22, wikipedia: 0.2 },
    { topic: 'Clotting', britannica: 0.1, wikipedia: 0.1 },
    { topic: 'Circulation', britannica: 0.18, wikipedia: 0.12 },
    { topic: 'Where blood is made', britannica: 0.14, wikipedia: 0.12 },
    { topic: 'Body heat', britannica: 0.1, wikipedia: 0.06 },
    { topic: 'Humours and temperament', britannica: 0.1, wikipedia: 0.04 },
    { topic: 'Bloodletting', britannica: 0.08, wikipedia: 0.06 },
    { topic: 'Transfusion', britannica: 0.08, wikipedia: 0.1 },
    { topic: 'Oxygen transport', britannica: 0, wikipedia: 0.12 },
    { topic: 'Disorders', britannica: 0, wikipedia: 0.08 },
  ],
  suggestedQuestions: [
    'What did people in 1797 get wrong about blood?',
    'Which facts about blood survived from 1797 to today?',
    "Is 'red globules' becoming 'red blood cells' new knowledge or just new words?",
  ],
  answers: {
    'What did people in 1797 get wrong about blood?': {
      answer:
        'Three claims in the 1797 entry no longer hold.\n\n' +
        '- Blood was thought to be made from chyle, the milky fluid of digestion [B4]. The cells are now known to be made in the bone marrow [W4].\n' +
        '- Its warmth was put down to fermentation or friction [B6]. Heat actually comes from metabolism in the liver and muscles; blood only carries it [W7].\n' +
        '- Bleeding a patient was routine treatment for "too great fulness of blood" [B7]. It is now kept for a few conditions [W9].\n\n' +
        'The entry is also silent on what blood carries. Oxygen transport by haemoglobin [W3] has no counterpart on the 1797 page.',
      citations: cite('B4', 'W4', 'B6', 'W7', 'B7', 'W9', 'W3'),
      grounding: 'supported',
    },
    'Which facts about blood survived from 1797 to today?': {
      answer:
        "The core anatomy has held up. Harvey's account of the heart driving blood out through the arteries and back by the veins [B5] matches the modern description of the circulation [W5].\n\n" +
        'The observation that drawn blood separates into a clot and a yellowish serum [B2] is still how serum is defined, under the same name [W6].\n\n' +
        "The red globules seen through Leeuwenhoek's microscope [B3] are today's red blood cells [W2]: the fact survived, the name did not.",
      citations: cite('B5', 'W5', 'B2', 'W6', 'B3', 'W2'),
      grounding: 'supported',
    },
    "Is 'red globules' becoming 'red blood cells' new knowledge or just new words?": {
      answer:
        'Mostly new words. The 1797 entry already knew the globules were tiny, red and floating in serum [B3]; Wikipedia describes the same objects as red blood cells, or erythrocytes [W2].\n\n' +
        'What is new is the knowledge attached to the name: the cells carry haemoglobin, which binds oxygen [W3], and they are made in the bone marrow and live about 120 days [W4]. The renaming is a change in language; what we know about the cells is a change in knowledge.',
      citations: cite('B3', 'W2', 'W3', 'W4'),
      grounding: 'supported',
    },
    'When was blood transfusion first tried?': {
      answer:
        'According to the 1797 entry, transfusion was first attempted in the 18th century, in England and France, and was stopped after some patients died [B8]. It became routine after the discovery of blood groups in 1901 [W8].',
      citations: cite('B8', 'W8'),
      grounding: 'supported',
    },
  },
}

const smallpox: MockTopic = {
  summary: {
    slug: 'smallpox',
    label: 'Smallpox',
    headword: 'SMALL-POX',
    edition: 'Second edition',
    year: 1778,
    match: 'strong',
    wikipediaTitle: 'Smallpox',
  },
  aliases: ['smallpox', 'small-pox', 'small pox', 'variola', 'inoculation'],
  britannica: {
    pageId: 'MOCK-0002',
    headword: 'SMALL-POX',
    edition: 'Second edition',
    year: 1778,
    volume: 'Volume 9',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, &c. - Second edition, Volume 9 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `SMA                    [ 7012 ]                    SMA

SMALT, a kind of glaſs of a deep blue colour, made
of zaffre, potaſh, and calcined flints.
  SMALL-POX, a contagious diſeaſe, attended with an
eruption of puſtules upon the ſkin, which, coming to
maturity, dry up and fall off in ſcabs. It was firſt de-
ſcribed by the Arabian phyſicians, and is now ſo uni-
verſal, that ſcarce one in a thouſand eſcapes it at ſome
period of life.
  Phyſicians divide it into the diſtinct and the con-
fluent kind. The confluent is by far the moſt dange-
rous, and carries off a great part of thoſe whom it ſeizes.
  The cauſe is ſuppoſed to be a peculiar ferment, re-
ceived into the blood, which, aſſimilating the humours
to its own nature, is at length thrown out upon the ſkin.
  The cure conſiſts chiefly in a cool regimen, frefh air,
and gentle pnrging; the hot method formerly in uſe, of
heaping clothes upon the patient, being now juſtly ex-
ploded. A perſon who has once had the diſeaſe is ſel-
dom or never ſeized with it a ſecond time.
  INOCULATION, or the ingrafting of the ſmall-pox, was
brought into England from Turkey by Lady Mary
Wortley Montagu about the year 1721; and experi-
ence has ſhown that of thoſe inoculated, ſcarce one in
ſeveral hundred dies.
  SMARAGDUS, the emerald. See Emerald.`,
    passages: [
      { id: 'B1', section: 'SMALL-POX', text: 'SMALL-POX, a contagious disease, attended with an eruption of pustules upon the skin, which, coming to maturity, dry up and fall off in scabs.' },
      { id: 'B2', section: 'SMALL-POX', text: 'It was first described by the Arabian physicians, and is now so universal, that scarce one in a thousand escapes it at some period of life.' },
      { id: 'B3', section: 'SMALL-POX', text: 'Physicians divide it into the distinct and the confluent kind. The confluent is by far the most dangerous, and carries off a great part of those whom it seizes.' },
      { id: 'B4', section: 'SMALL-POX', text: 'The cause is supposed to be a peculiar ferment, received into the blood, which, assimilating the humours to its own nature, is at length thrown out upon the skin.' },
      { id: 'B5', section: 'SMALL-POX', text: 'The cure consists chiefly in a cool regimen, fresh air, and gentle purging; the hot method formerly in use, of heaping clothes upon the patient, being now justly exploded.' },
      { id: 'B6', section: 'SMALL-POX', text: 'A person who has once had the disease is seldom or never seized with it a second time.' },
      { id: 'B7', section: 'INOCULATION', text: 'Inoculation, or the ingrafting of the small-pox, was brought into England from Turkey by Lady Mary Wortley Montagu about the year 1721; and experience has shown that of those inoculated, scarce one in several hundred dies.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-smallpox',
    title: 'Smallpox',
    url: wiki('Smallpox'),
    dateModified: '2026-09-21',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Smallpox was an infectious disease caused by variola virus. The last natural case was diagnosed in 1977, and the World Health Organization certified the disease eradicated in 1980.' },
      { id: 'W2', section: 'Signs and symptoms', text: 'The illness began with fever and vomiting, followed by a rash that became fluid-filled blisters and then scabbed over, often leaving deep scars.' },
      { id: 'W3', section: 'Classification', text: 'Variola major killed about 30% of those infected. Its flat and haemorrhagic forms were usually fatal.' },
      { id: 'W4', section: 'Transmission', text: 'The virus spread between people in respiratory droplets and through contact with contaminated bedding and clothing.' },
      { id: 'W5', section: 'Variolation', text: 'Variolation, deliberately infecting a person with material from a smallpox sore, was practised in Asia and Africa and was introduced to Britain in 1721 by Lady Mary Wortley Montagu. It killed far fewer people than natural smallpox, but some still died.' },
      { id: 'W6', section: 'Vaccination', text: 'In 1796 Edward Jenner showed that inoculation with cowpox protected against smallpox. It was the first vaccine; the word comes from the Latin vacca, cow.' },
      { id: 'W7', section: 'Treatment', text: 'No treatment was proven to cure smallpox; care was supportive. Survivors had lasting immunity.' },
      { id: 'W8', section: 'Eradication', text: 'A worldwide vaccination campaign led by the WHO ended natural transmission. Smallpox is one of only two infectious diseases to have been eradicated, the other being rinderpest.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.84,
    rerankScore: 0.9,
    reasons: [
      'Same headword once the hyphen is dropped: SMALL-POX and Smallpox.',
      'Rare terms appear in both: scabs, inoculation, Montagu, 1721.',
      'Variolation also scores well, but only for the INOCULATION sub-entry, so it is listed as a second candidate.',
    ],
  },
  candidates: [
    { title: 'Variolation', url: wiki('Variolation'), embedScore: 0.81, rerankScore: 0.72 },
    { title: 'Smallpox vaccine', url: wiki('Smallpox vaccine'), embedScore: 0.73, rerankScore: 0.58 },
    { title: 'Edward Jenner', url: wiki('Edward Jenner'), embedScore: 0.66, rerankScore: 0.41 },
  ],
  alignments: [
    { id: 's1', kind: 'retained', verdict: 'correct', label: 'The rash', britannica: { passageId: 'B1', quote: 'an eruption of pustules upon the skin, which, coming to maturity, dry up and fall off in scabs' }, wikipedia: { passageId: 'W2', quote: 'a rash that became fluid-filled blisters and then scabbed over' }, note: 'The visible course of the disease is described the same way in both.' },
    { id: 's2', kind: 'reworded', verdict: 'correct', label: 'Inoculation', britannica: { passageId: 'B7', quote: 'Inoculation, or the ingrafting of the small-pox' }, wikipedia: { passageId: 'W5', quote: 'Variolation' }, note: 'Same practice, new name. "Inoculation" now means any vaccine, so the smallpox-on-smallpox method is called variolation.' },
    { id: 's3', kind: 'retained', verdict: 'correct', label: 'Lady Mary Wortley Montagu', britannica: { passageId: 'B7', quote: 'brought into England from Turkey by Lady Mary Wortley Montagu about the year 1721' }, wikipedia: { passageId: 'W5', quote: 'introduced to Britain in 1721 by Lady Mary Wortley Montagu' }, note: 'Same person, same year.' },
    { id: 's4', kind: 'reworded', verdict: 'correct', label: 'Two kinds of smallpox', britannica: { passageId: 'B3', quote: 'The confluent is by far the most dangerous' }, wikipedia: { passageId: 'W3', quote: 'Its flat and haemorrhagic forms were usually fatal' }, note: 'Both sort cases by severity. The categories have new names and now come with a death rate.' },
    { id: 's5', kind: 'revised', verdict: 'wrong', label: 'The cause', britannica: { passageId: 'B4', quote: 'a peculiar ferment, received into the blood' }, wikipedia: { passageId: 'W1', quote: 'caused by variola virus' }, note: 'A "ferment" that turns the humours is replaced by a virus. Germ theory arrived about a century after this edition.' },
    { id: 's6', kind: 'reworded', verdict: 'correct', label: 'Immunity', britannica: { passageId: 'B6', quote: 'seldom or never seized with it a second time' }, wikipedia: { passageId: 'W7', quote: 'Survivors had lasting immunity' }, note: 'The same observation. "Immunity" names the mechanism behind it.' },
    { id: 's7', kind: 'revised', verdict: 'wrong', label: 'The cure', britannica: { passageId: 'B5', quote: 'The cure consists chiefly in a cool regimen, fresh air, and gentle purging' }, wikipedia: { passageId: 'W7', quote: 'No treatment was proven to cure smallpox' }, note: 'In 1778 a cooling regimen was thought to cure it. Nothing ever did; prevention is what worked.' },
    { id: 's8', kind: 'revised', verdict: 'partly', label: 'How common it is', britannica: { passageId: 'B2', quote: 'scarce one in a thousand escapes it' }, wikipedia: { passageId: 'W1', quote: 'certified the disease eradicated in 1980' }, note: 'True in 1778, no longer: the disease was eradicated in 1980. The world changed more than the knowledge.' },
    { id: 's9', kind: 'added', verdict: null, label: 'Vaccination', britannica: null, wikipedia: { passageId: 'W6', quote: 'In 1796 Edward Jenner showed that inoculation with cowpox protected against smallpox' }, note: "Jenner's work came 18 years after this edition." },
    { id: 's10', kind: 'added', verdict: null, label: 'How it spreads', britannica: null, wikipedia: { passageId: 'W4', quote: 'spread between people in respiratory droplets' }, note: 'The 1778 entry calls it contagious but never says how it passes between people.' },
  ],
  coverage: [
    { topic: 'Symptoms', britannica: 0.2, wikipedia: 0.12 },
    { topic: 'Kinds and severity', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Cause', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Treatment', britannica: 0.15, wikipedia: 0.08 },
    { topic: 'Immunity', britannica: 0.08, wikipedia: 0.06 },
    { topic: 'Inoculation', britannica: 0.2, wikipedia: 0.14 },
    { topic: 'How common it is', britannica: 0.07, wikipedia: 0 },
    { topic: 'Vaccination', britannica: 0, wikipedia: 0.15 },
    { topic: 'Transmission', britannica: 0, wikipedia: 0.1 },
    { topic: 'Eradication', britannica: 0, wikipedia: 0.15 },
  ],
  suggestedQuestions: [
    'How did people try to prevent smallpox in 1778, and what replaced it?',
    'What did the 1778 entry believe caused smallpox?',
    "Is 'inoculation' in 1778 the same thing as a vaccine today?",
  ],
  answers: {
    'How did people try to prevent smallpox in 1778, and what replaced it?': {
      answer:
        'In 1778 the method was inoculation, also called ingrafting: giving a healthy person matter from a smallpox case so they caught a milder form [B7]. Wikipedia calls the same practice variolation and, like the 1778 entry, credits Lady Mary Wortley Montagu with bringing it to Britain in 1721 [W5].\n\n' +
        'It was replaced by vaccination. In 1796, after this edition, Edward Jenner showed that cowpox gave protection [W6], and a worldwide vaccination campaign later ended the disease [W8].',
      citations: cite('B7', 'W5', 'W6', 'W8'),
      grounding: 'supported',
    },
    'What did the 1778 entry believe caused smallpox?': {
      answer:
        'A "peculiar ferment" received into the blood, which turned the humours to its own nature and was then pushed out through the skin [B4]. Wikipedia names a virus, variola, as the cause [W1].\n\n' +
        'This is a change in knowledge, not in wording: the ferment and the humours have no modern counterpart.',
      citations: cite('B4', 'W1'),
      grounding: 'supported',
    },
    "Is 'inoculation' in 1778 the same thing as a vaccine today?": {
      answer:
        'No. In 1778 "inoculation" meant ingrafting real smallpox matter [B7], which still killed some patients [W5]. The first vaccine used cowpox instead [W6].\n\n' +
        'The word stayed while what it describes changed, so a reader who sees "inoculation" in both texts may assume a continuity that is not there.',
      citations: cite('B7', 'W5', 'W6'),
      grounding: 'supported',
    },
    'How was smallpox treated in 1778?': {
      answer: 'The 1778 entry does not describe a treatment for smallpox. Wikipedia says no treatment was ever proven to cure it and care was supportive [W7].',
      citations: cite('W7'),
      grounding: 'partial',
    },
  },
}

const consumption: MockTopic = {
  summary: {
    slug: 'consumption',
    label: 'Consumption',
    headword: 'CONSUMPTION',
    edition: 'Seventh edition',
    year: 1842,
    match: 'strong',
    wikipediaTitle: 'Tuberculosis',
  },
  aliases: ['consumption', 'phthisis', 'tuberculosis', 'tb', 'phthisis pulmonalis'],
  britannica: {
    pageId: 'MOCK-0003',
    headword: 'CONSUMPTION',
    edition: 'Seventh edition',
    year: 1842,
    volume: 'Volume 7',
    meta: 'Encyclopaedia Britannica - Seventh edition, Volume 7 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `CONSUMPTION.                    621

ſtated, that the produce of the duty on spirits con-
sumed in Scotland
  CONSUMPTION, or PHTHISIS PULMONALIS, a wast-
ing of the body, attended with hectic fever, cough, and
an expectoration of purulent matter from the lungs. It
is the most fatal of all the diseases of tliis climate; it
has been computed that nearly one-fourth of the deaths
in Britain arise from it.
  On dissection the lungs are found studded with tu-
bercles, small hard bodies which afterwards soften and
form ulcers, or vomicæ. The disease is very frequently
hereditary; and persons of a fair complexion, a long
neck, and a narrow chest are thought especially dis-
posed to it.
  Whether it be contagious has been much disputed.
In Italy and Spain the clothes of consumptive persons
are burned; but in this country the opinion is gene-
rally rejected. The stethoscope of Laennec enables the
physician to detect the cavities of the lungs by the
sounds of the breath and of the voice.
  Change of climate, a sea voyage, exercise on horse-
back, and a diet of milk are recommended; but when
the disease is confirmed it is seldom cured.
  See MEDICINE, Index.`,
    passages: [
      { id: 'B1', section: 'CONSUMPTION', text: 'CONSUMPTION, or PHTHISIS PULMONALIS, a wasting of the body, attended with hectic fever, cough, and an expectoration of purulent matter from the lungs.' },
      { id: 'B2', section: 'CONSUMPTION', text: 'It is the most fatal of all the diseases of this climate; it has been computed that nearly one-fourth of the deaths in Britain arise from it.' },
      { id: 'B3', section: 'CONSUMPTION', text: 'On dissection the lungs are found studded with tubercles, small hard bodies which afterwards soften and form ulcers, or vomicae.' },
      { id: 'B4', section: 'CONSUMPTION', text: 'The disease is very frequently hereditary; and persons of a fair complexion, a long neck, and a narrow chest are thought especially disposed to it.' },
      { id: 'B5', section: 'CONSUMPTION', text: 'Whether it be contagious has been much disputed. In Italy and Spain the clothes of consumptive persons are burned; but in this country the opinion is generally rejected.' },
      { id: 'B6', section: 'CONSUMPTION', text: 'The stethoscope of Laennec enables the physician to detect the cavities of the lungs by the sounds of the breath and of the voice.' },
      { id: 'B7', section: 'CONSUMPTION', text: 'Change of climate, a sea voyage, exercise on horseback, and a diet of milk are recommended; but when the disease is confirmed it is seldom cured.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-tuberculosis',
    title: 'Tuberculosis',
    url: wiki('Tuberculosis'),
    dateModified: '2026-10-02',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Tuberculosis (TB) is an infectious disease usually caused by Mycobacterium tuberculosis bacteria. It mainly affects the lungs. It was historically called consumption because of the weight loss it causes.' },
      { id: 'W2', section: 'Signs and symptoms', text: 'Active TB causes a chronic cough with blood-containing mucus, fever, night sweats and weight loss.' },
      { id: 'W3', section: 'Transmission', text: 'It spreads through the air when people with active TB in their lungs cough, speak or sneeze. Robert Koch identified the bacterium in 1882.' },
      { id: 'W4', section: 'Latent infection', text: 'Most infections cause no symptoms, a state called latent tuberculosis. About one in ten latent infections progresses to active disease.' },
      { id: 'W5', section: 'Risk factors', text: 'Risk factors include HIV, malnutrition, smoking, diabetes and crowded housing. Genes affect susceptibility, but the disease itself is not inherited.' },
      { id: 'W6', section: 'Pathology', text: 'The body walls off the bacteria in granulomas, small nodules called tubercles, which can break down and leave cavities in the lung.' },
      { id: 'W7', section: 'Diagnosis', text: 'Diagnosis relies on chest X-rays, sputum microscopy and culture, and molecular tests.' },
      { id: 'W8', section: 'Treatment', text: 'Treatment is a course of several antibiotics taken for months. Streptomycin, introduced in the 1940s, was the first effective drug. Drug-resistant TB is a growing problem.' },
      { id: 'W9', section: 'History', text: 'Before antibiotics, patients were sent to sanatoria for rest, fresh air and good food.' },
      { id: 'W10', section: 'Epidemiology', text: 'It remains one of the leading infectious causes of death worldwide.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.78,
    rerankScore: 0.88,
    reasons: [
      'Different headwords: CONSUMPTION and Tuberculosis. Matched on content, not title.',
      'The Wikipedia introduction says the disease was historically called consumption.',
      'Consumption (economics) shares the title but the reranker scores it 0.04.',
    ],
  },
  candidates: [
    { title: 'History of tuberculosis', url: wiki('History of tuberculosis'), embedScore: 0.8, rerankScore: 0.81 },
    { title: 'Cachexia', url: wiki('Cachexia'), embedScore: 0.64, rerankScore: 0.29 },
    { title: 'Consumption (economics)', url: wiki('Consumption (economics)'), embedScore: 0.58, rerankScore: 0.04 },
  ],
  alignments: [
    { id: 'c1', kind: 'reworded', verdict: 'correct', label: 'The name', britannica: { passageId: 'B1', quote: 'CONSUMPTION, or PHTHISIS PULMONALIS' }, wikipedia: { passageId: 'W1', quote: 'It was historically called consumption' }, note: 'The same disease under its old names. The modern name comes from the tubercles described on this page.' },
    { id: 'c2', kind: 'retained', verdict: 'correct', label: 'Symptoms', britannica: { passageId: 'B1', quote: 'hectic fever, cough, and an expectoration of purulent matter' }, wikipedia: { passageId: 'W2', quote: 'a chronic cough with blood-containing mucus, fever, night sweats and weight loss' }, note: 'The symptoms are described alike.' },
    { id: 'c3', kind: 'retained', verdict: 'correct', label: 'Tubercles', britannica: { passageId: 'B3', quote: 'the lungs are found studded with tubercles' }, wikipedia: { passageId: 'W6', quote: 'small nodules called tubercles' }, note: 'Same word, same finding. Wikipedia adds that they are the body walling off bacteria.' },
    { id: 'c4', kind: 'revised', verdict: 'wrong', label: 'Is it inherited?', britannica: { passageId: 'B4', quote: 'The disease is very frequently hereditary' }, wikipedia: { passageId: 'W5', quote: 'the disease itself is not inherited' }, note: 'Families shared the disease because they shared air and housing, not because it was inherited.' },
    { id: 'c5', kind: 'revised', verdict: 'wrong', label: 'Is it contagious?', britannica: { passageId: 'B5', quote: 'in this country the opinion is generally rejected' }, wikipedia: { passageId: 'W3', quote: 'It spreads through the air' }, note: "The biggest reversal on the page. Britain rejected contagion in 1842; Koch's bacterium settled it forty years later." },
    { id: 'c6', kind: 'revised', verdict: 'partly', label: 'Can it be cured?', britannica: { passageId: 'B7', quote: 'when the disease is confirmed it is seldom cured' }, wikipedia: { passageId: 'W8', quote: 'Treatment is a course of several antibiotics taken for months' }, note: 'True in 1842, when there was no cure. Curable since the 1940s, though drug resistance is eroding that.' },
    { id: 'c7', kind: 'reworded', verdict: 'partly', label: 'Rest and fresh air', britannica: { passageId: 'B7', quote: 'Change of climate, a sea voyage, exercise on horseback, and a diet of milk' }, wikipedia: { passageId: 'W9', quote: 'sanatoria for rest, fresh air and good food' }, note: 'Rest and food helped, but cured no one. The same regimen later moved into sanatoria.' },
    { id: 'c8', kind: 'revised', verdict: 'correct', label: 'Diagnosis', britannica: { passageId: 'B6', quote: 'The stethoscope of Laennec' }, wikipedia: { passageId: 'W7', quote: 'chest X-rays, sputum microscopy and culture, and molecular tests' }, note: 'Listening to the chest gave way to seeing the lungs and the bacterium.' },
    { id: 'c9', kind: 'retained', verdict: 'partly', label: 'How deadly it is', britannica: { passageId: 'B2', quote: 'nearly one-fourth of the deaths in Britain' }, wikipedia: { passageId: 'W10', quote: 'one of the leading infectious causes of death worldwide' }, note: 'Still a leading killer, but no longer of Britain: the burden moved, the fact did not.' },
    { id: 'c10', kind: 'dropped', verdict: 'wrong', label: 'Who is disposed to it', britannica: { passageId: 'B4', quote: 'persons of a fair complexion, a long neck, and a narrow chest' }, wikipedia: null, note: 'This body-type profile has no place among modern risk factors.' },
    { id: 'c11', kind: 'added', verdict: null, label: 'Latent infection', britannica: null, wikipedia: { passageId: 'W4', quote: 'Most infections cause no symptoms' }, note: 'Infection without disease could not be seen before the bacterium was known.' },
  ],
  coverage: [
    { topic: 'Symptoms', britannica: 0.18, wikipedia: 0.1 },
    { topic: 'How deadly it is', britannica: 0.12, wikipedia: 0.06 },
    { topic: 'Pathology', britannica: 0.14, wikipedia: 0.1 },
    { topic: 'Heredity and body type', britannica: 0.16, wikipedia: 0.05 },
    { topic: 'Contagion', britannica: 0.14, wikipedia: 0.12 },
    { topic: 'Diagnosis', britannica: 0.12, wikipedia: 0.08 },
    { topic: 'Treatment', britannica: 0.14, wikipedia: 0.16 },
    { topic: 'Cause (bacterium)', britannica: 0, wikipedia: 0.12 },
    { topic: 'Latent infection', britannica: 0, wikipedia: 0.1 },
    { topic: 'Drug resistance', britannica: 0, wikipedia: 0.11 },
  ],
  suggestedQuestions: [
    'Did people in 1842 think consumption was contagious?',
    'Who did the 1842 entry say gets consumption, and is that still true?',
    'How did treatment change between 1842 and today?',
  ],
  answers: {
    'Did people in 1842 think consumption was contagious?': {
      answer:
        'Mostly not, in Britain. The entry says contagion "has been much disputed": in Italy and Spain the clothes of consumptive people were burned, but in Britain the idea was generally rejected [B5].\n\n' +
        'Wikipedia states that the disease spreads through the air, and that Robert Koch identified the bacterium in 1882 [W3], forty years after this edition.',
      citations: cite('B5', 'W3'),
      grounding: 'supported',
    },
    'Who did the 1842 entry say gets consumption, and is that still true?': {
      answer:
        'It says the disease is very often hereditary, and that people with a fair complexion, a long neck and a narrow chest are especially prone to it [B4].\n\n' +
        'Neither holds. Wikipedia lists HIV, malnutrition, smoking, diabetes and crowded housing as risk factors, and says genes affect susceptibility but the disease is not inherited [W5]. Families were sharing air, not genes, which is how the 1842 view could form from honest observation.',
      citations: cite('B4', 'W5'),
      grounding: 'supported',
    },
    'How did treatment change between 1842 and today?': {
      answer:
        'In 1842 the advice was a change of climate, a sea voyage, riding and a milk diet, with the warning that confirmed cases were seldom cured [B7]. The same idea of rest and fresh air later moved into sanatoria [W9].\n\n' +
        'Real treatment arrived with antibiotics: a months-long course of several drugs, starting with streptomycin in the 1940s [W8].',
      citations: cite('B7', 'W9', 'W8'),
      grounding: 'supported',
    },
  },
}

const animalMagnetism: MockTopic = {
  summary: {
    slug: 'animal-magnetism',
    label: 'Animal magnetism',
    headword: 'ANIMAL MAGNETISM',
    edition: 'Supplement to the 4th–6th editions',
    year: 1824,
    match: 'partial',
    wikipediaTitle: 'Animal magnetism',
  },
  aliases: ['animal magnetism', 'mesmerism', 'magnetism'],
  britannica: {
    pageId: 'MOCK-0004',
    headword: 'ANIMAL MAGNETISM',
    edition: 'Supplement to the 4th–6th editions',
    year: 1824,
    volume: 'Volume 1',
    meta: 'Supplement to the fourth, fifth and sixth editions of the Encyclopaedia Britannica - Volume 1 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `ANIMAL MAGNETISM.                    329

  ANIMAL MAGNETISM, a pretended power, by which
one person, through certain motions of the hands, is
said to produce extraordinary effects upon the body of
another, and even to cure diseases. It was brought into
notice at Vienna, and afterwards at Paris, by Mesmer,
about the year 1778, whence it is also called Mesmerism.
  In 1784 commissioners appointed by the King of France,
among whom was Dr Franklin, reported that the effects
were owing to the imagination alone, and that the sup-
posed fluid had no existence. Its partisans are never-
theless still numerous in Germany, where it is employed
by some physicians in the treatment of nervous com-
plaints.
  ANIMALCULE, a name given to animals so small as
to be invisible to the naked eye. See Microscope.`,
    passages: [
      { id: 'B1', section: 'ANIMAL MAGNETISM', text: 'ANIMAL MAGNETISM, a pretended power, by which one person, through certain motions of the hands, is said to produce extraordinary effects upon the body of another, and even to cure diseases.' },
      { id: 'B2', section: 'ANIMAL MAGNETISM', text: 'It was brought into notice at Vienna, and afterwards at Paris, by Mesmer, about the year 1778, whence it is also called Mesmerism.' },
      { id: 'B3', section: 'ANIMAL MAGNETISM', text: 'In 1784 commissioners appointed by the King of France, among whom was Dr Franklin, reported that the effects were owing to the imagination alone, and that the supposed fluid had no existence.' },
      { id: 'B4', section: 'ANIMAL MAGNETISM', text: 'Its partisans are nevertheless still numerous in Germany, where it is employed by some physicians in the treatment of nervous complaints.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-animal-magnetism',
    title: 'Animal magnetism',
    url: wiki('Animal magnetism'),
    dateModified: '2026-08-14',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Animal magnetism, also called mesmerism, was a theory put forward by Franz Mesmer in the 18th century that an invisible natural force passes between living things.' },
      { id: 'W2', section: 'Investigation', text: 'A French royal commission in 1784, which included Benjamin Franklin and Antoine Lavoisier, found no evidence of the fluid and attributed the effects to imagination.' },
      { id: 'W3', section: 'Legacy', text: 'The theory is regarded as pseudoscience. Some of its techniques fed into the later practice of hypnosis.' },
      { id: 'W4', section: 'Explanation', text: 'Researchers now attribute the reported effects to suggestion and the placebo effect.' },
    ],
  },
  match: {
    strength: 'partial',
    embedScore: 0.81,
    rerankScore: 0.64,
    reasons: [
      'Same title, but Wikipedia treats animal magnetism as history, not as current medicine.',
      'There is no modern medical article on this subject, so the differences are mostly about framing, not new medical knowledge.',
      'Hypnosis (0.52) and Placebo (0.41) cover what the effects are now thought to be.',
    ],
  },
  candidates: [
    { title: 'Franz Mesmer', url: wiki('Franz Mesmer'), embedScore: 0.77, rerankScore: 0.6 },
    { title: 'Hypnosis', url: wiki('Hypnosis'), embedScore: 0.69, rerankScore: 0.52 },
    { title: 'Placebo', url: wiki('Placebo'), embedScore: 0.61, rerankScore: 0.41 },
  ],
  alignments: [
    { id: 'm1', kind: 'reworded', verdict: 'correct', label: 'What it is', britannica: { passageId: 'B1', quote: 'a pretended power' }, wikipedia: { passageId: 'W3', quote: 'regarded as pseudoscience' }, note: 'Both texts doubt it. 1824 says "pretended"; the modern word is "pseudoscience".' },
    { id: 'm2', kind: 'retained', verdict: 'correct', label: 'Mesmer', britannica: { passageId: 'B2', quote: 'by Mesmer, about the year 1778' }, wikipedia: { passageId: 'W1', quote: 'put forward by Franz Mesmer in the 18th century' }, note: 'Same origin story.' },
    { id: 'm3', kind: 'retained', verdict: 'correct', label: 'The 1784 commission', britannica: { passageId: 'B3', quote: 'the effects were owing to the imagination alone' }, wikipedia: { passageId: 'W2', quote: 'attributed the effects to imagination' }, note: 'The verdict is reported the same way in both.' },
    { id: 'm4', kind: 'revised', verdict: 'wrong', label: 'Medical use', britannica: { passageId: 'B4', quote: 'employed by some physicians in the treatment of nervous complaints' }, wikipedia: { passageId: 'W4', quote: 'suggestion and the placebo effect' }, note: 'A treatment some doctors still used in 1824; now an example of suggestion.' },
    { id: 'm5', kind: 'added', verdict: null, label: 'Hypnosis', britannica: null, wikipedia: { passageId: 'W3', quote: 'fed into the later practice of hypnosis' }, note: 'The link to hypnosis came after 1824.' },
  ],
  coverage: [
    { topic: 'What it claims', britannica: 0.3, wikipedia: 0.22 },
    { topic: 'Origin', britannica: 0.22, wikipedia: 0.2 },
    { topic: '1784 commission', britannica: 0.26, wikipedia: 0.24 },
    { topic: 'Medical use', britannica: 0.22, wikipedia: 0 },
    { topic: 'Scientific status', britannica: 0, wikipedia: 0.18 },
    { topic: 'Hypnosis and placebo', britannica: 0, wikipedia: 0.16 },
  ],
  suggestedQuestions: [
    'Did the 1824 entry believe animal magnetism was real?',
    'What is the modern medical treatment that replaced animal magnetism?',
  ],
  answers: {
    'Did the 1824 entry believe animal magnetism was real?': {
      answer:
        'No. It calls animal magnetism "a pretended power" [B1] and reports the 1784 French commission, including Benjamin Franklin, finding the effects due to imagination alone [B3]. Wikipedia gives the same verdict [W2] and calls the theory pseudoscience [W3].\n\n' +
        'So the scepticism is not new. What changed is the explanation: suggestion and the placebo effect [W4].',
      citations: cite('B1', 'B3', 'W2', 'W3', 'W4'),
      grounding: 'supported',
    },
    'What is the modern medical treatment that replaced animal magnetism?': {
      answer:
        'The sources do not support an answer. The 1824 entry mentions use for "nervous complaints" [B4], but the Wikipedia article treats animal magnetism as history and names no treatment that replaced it. Hypnosis is mentioned only as a later practice its techniques fed into [W3].',
      citations: cite('B4', 'W3'),
      grounding: 'unsupported',
    },
  },
}

const animalSpirits: MockTopic = {
  summary: {
    slug: 'animal-spirits',
    label: 'Animal spirits',
    headword: 'ANIMAL SPIRITS',
    edition: 'Third edition',
    year: 1797,
    match: 'none',
    wikipediaTitle: null,
  },
  aliases: ['animal spirits', 'spirits', 'nervous fluid', 'nervous power'],
  britannica: {
    pageId: 'MOCK-0005',
    headword: 'ANIMAL SPIRITS',
    edition: 'Third edition',
    year: 1797,
    volume: 'Volume 17',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, and miscellaneous literature - Third edition, Volume 17 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `SPI                    [ 712 ]                    SPI

  SPIRITS, ANIMAL, a fine ſubtile fluid, ſuppoſed to be
ſeparated from the blood in the brain, and conveyed
by the nerves to every part of the body, as the inſtru-
ment of ſenſation and muſcular motion.
  Their exiſtence has never been demonſtrated, for no
fluid has been found in the nerves even by the beſt mi-
croſcopes; yet the hypotheſis is retained by many as
the eaſieſt explanation of the phenomena. Some late
authors have ſuppoſed the nervous power to be of the
ſame nature with the electric fluid. See Nerves.
  SPIRITS of WINE. See Alcohol.`,
    passages: [
      { id: 'B1', section: 'SPIRITS, ANIMAL', text: 'ANIMAL SPIRITS, a fine subtile fluid, supposed to be separated from the blood in the brain, and conveyed by the nerves to every part of the body, as the instrument of sensation and muscular motion.' },
      { id: 'B2', section: 'SPIRITS, ANIMAL', text: 'Their existence has never been demonstrated, for no fluid has been found in the nerves even by the best microscopes; yet the hypothesis is retained by many as the easiest explanation of the phenomena.' },
      { id: 'B3', section: 'SPIRITS, ANIMAL', text: 'Some late authors have supposed the nervous power to be of the same nature with the electric fluid.' },
    ],
  },
  wikipedia: null,
  match: {
    strength: 'none',
    embedScore: 0.71,
    rerankScore: 0.12,
    reasons: [
      'The title match, Animal spirits (Keynes), is about economics. The reranker scores it 0.12.',
      'Pneuma covers the ancient idea, but not the 18th-century medical theory.',
      'No candidate passes the 0.5 rerank threshold, so no comparison is drawn.',
    ],
  },
  candidates: [
    { title: 'Animal spirits (Keynes)', url: wiki('Animal spirits (Keynes)'), embedScore: 0.71, rerankScore: 0.12 },
    { title: 'Pneuma', url: wiki('Pneuma'), embedScore: 0.62, rerankScore: 0.38 },
    { title: 'Nervous system', url: wiki('Nervous system'), embedScore: 0.6, rerankScore: 0.35 },
  ],
  alignments: [],
  coverage: [
    { topic: 'What the spirits are', britannica: 0.45, wikipedia: 0 },
    { topic: 'Evidence', britannica: 0.35, wikipedia: 0 },
    { topic: 'Electricity', britannica: 0.2, wikipedia: 0 },
  ],
  suggestedQuestions: ['What is the modern view of animal spirits?', 'What did the 1797 entry think carried sensation along the nerves?'],
  answers: {
    'What is the modern view of animal spirits?': {
      answer:
        'Today "animal spirits" describes the emotions and instincts that drive economic decisions, such as consumer confidence and investment.\n\n' +
        'No Wikipedia article on this page is a credible counterpart; this answer came from the economics article that the reranker scored 0.12.',
      citations: [],
      grounding: 'unsupported',
    },
    'What did the 1797 entry think carried sensation along the nerves?': {
      answer:
        'A "fine subtile fluid" separated from the blood in the brain and sent along the nerves [B1]. The entry admits no such fluid had ever been found [B2], and notes that some authors thought the nervous power was electrical [B3].\n\n' +
        'There is no matched Wikipedia article to compare against, so the agent cannot say from the sources how this changed.',
      citations: cite('B1', 'B2', 'B3'),
      grounding: 'partial',
    },
  },
}

export const MOCK_TOPICS: MockTopic[] = [blood, smallpox, consumption, animalMagnetism, animalSpirits]
