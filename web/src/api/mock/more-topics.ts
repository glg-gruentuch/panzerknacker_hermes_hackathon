import type { ChatResponse } from '../types'
import type { MockTopic } from './topics'

// MOCK DATA for the geology and natural-science areas. Same rules as topics.ts:
// the Britannica passages are written in period style for the demo, not OCR
// from the dataset; the Wikipedia passages paraphrase the articles.

const wiki = (title: string) => `https://en.wikipedia.org/wiki/${title.replace(/ /g, '_')}`

const cite = (...ids: string[]): ChatResponse['citations'] =>
  ids.map((id, i) => ({
    id,
    source: id.startsWith('B') ? 'britannica' : 'wikipedia',
    passageId: id,
    rerankScore: Math.round((0.93 - i * 0.04) * 100) / 100,
  }))

const basalt: MockTopic = {
  summary: {
    slug: 'basalt',
    label: 'Basalt',
    headword: 'BASALTES',
    edition: 'Third edition',
    year: 1797,
    match: 'strong',
    wikipediaTitle: 'Basalt',
    area: 'geology',
    teaser: 'Concerning the origin of this stone naturalists are much divided.',
  },
  aliases: ['basalt', 'basaltes', "giant's causeway"],
  britannica: {
    pageId: 'MOCK-0006',
    headword: 'BASALTES',
    edition: 'Third edition',
    year: 1797,
    volume: 'Volume 2',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, and miscellaneous literature - Third edition, Volume 2 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `BAS                    [ 112 ]                    BAS

the ſea-coaſt, where the town is ſituated. Long. 9. 30. E.
  BASALTES, in natural hiſtory, a heavy and hard ſtone,
of a black or dark grey colour, which is found in co-
lumns of three, four, five, ſix or ſeven ſides, ſtanding
cloſe together. The moſt remarkable collection of theſe
columns is the Giant's Cauſeway, in the county of An-
trim in Ireland, where many thouſands of them ſtand
ſide by ſide, as if ſet there by art.
  Concerning the origin of this ſtone naturaliſts are
much divided. Some hold it to be a production of fire,
and the columns to have been formed by the cooling
of a melted maſs; others, with greater probability, a
cryſtallization from water.
  It ſtrikes fire with ſteel, does not effervesce with
acids, and melts in a ſtrong fire into a black glaſs. It
is uſed by the jewellers as a touchſtone for trying gold
and ſilver, and for mortars, and the ancients made ſta-
tues of it.
  BASANITES. See Basaltes.`,
    passages: [
      { id: 'B1', section: 'BASALTES', text: 'BASALTES, in natural history, a heavy and hard stone, of a black or dark grey colour, which is found in columns of three, four, five, six or seven sides, standing close together.' },
      { id: 'B2', section: 'BASALTES', text: "The most remarkable collection of these columns is the Giant's Causeway, in the county of Antrim in Ireland, where many thousands of them stand side by side, as if set there by art." },
      { id: 'B3', section: 'BASALTES', text: 'Concerning the origin of this stone naturalists are much divided. Some hold it to be a production of fire, and the columns to have been formed by the cooling of a melted mass; others, with greater probability, a crystallization from water.' },
      { id: 'B4', section: 'BASALTES', text: 'It strikes fire with steel, does not effervesce with acids, and melts in a strong fire into a black glass.' },
      { id: 'B5', section: 'BASALTES', text: 'It is used by the jewellers as a touchstone for trying gold and silver, and for mortars, and the ancients made statues of it.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-basalt',
    title: 'Basalt',
    url: wiki('Basalt'),
    dateModified: '2026-09-12',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Basalt is a fine-grained volcanic rock formed from the rapid cooling of lava rich in magnesium and iron. It is the most common volcanic rock on Earth.' },
      { id: 'W2', section: 'Columnar jointing', text: "When a thick lava flow cools, it contracts and cracks into polygonal columns, usually with five or six sides. The Giant's Causeway in Northern Ireland is a well-known example." },
      { id: 'W3', section: 'History', text: 'In the late 18th century, Neptunists argued that basalt had crystallized from an ancient ocean, while Plutonists held that it formed from molten rock. Field studies of extinct volcanoes settled the question in favour of a volcanic origin.' },
      { id: 'W4', section: 'Properties', text: 'Basalt is dark grey to black. It melts at roughly 1,000 to 1,250 °C, and basalt that cools very fast forms a black volcanic glass.' },
      { id: 'W5', section: 'Distribution', text: 'Basalt makes up most of the ocean floor, and large basalt plains cover parts of the Moon and Mars.' },
      { id: 'W6', section: 'Uses', text: 'Crushed basalt is used as aggregate in roads, railway ballast and concrete, and polished basalt as building stone.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.83,
    rerankScore: 0.9,
    reasons: [
      'Same headword once the Latin ending is dropped: BASALTES and Basalt.',
      "Both describe the columns and name the Giant's Causeway.",
      'Columnar jointing scores close behind, but covers only the columns, not the rock.',
    ],
  },
  candidates: [
    { title: 'Columnar jointing', url: wiki('Columnar jointing'), embedScore: 0.8, rerankScore: 0.7 },
    { title: "Giant's Causeway", url: wiki("Giant's Causeway"), embedScore: 0.76, rerankScore: 0.6 },
    { title: 'Neptunism', url: wiki('Neptunism'), embedScore: 0.7, rerankScore: 0.52 },
  ],
  alignments: [
    { id: 'b1', kind: 'retained', verdict: 'correct', label: 'Columns', britannica: { passageId: 'B1', quote: 'found in columns of three, four, five, six or seven sides' }, wikipedia: { passageId: 'W2', quote: 'cracks into polygonal columns, usually with five or six sides' }, note: 'The same columns, described the same way. Today they have a name: columnar jointing.' },
    { id: 'b2', kind: 'retained', verdict: 'correct', label: "Giant's Causeway", britannica: { passageId: 'B2', quote: "the Giant's Causeway, in the county of Antrim in Ireland" }, wikipedia: { passageId: 'W2', quote: "The Giant's Causeway in Northern Ireland" }, note: 'The example both texts reach for first.' },
    { id: 'b3', kind: 'revised', verdict: 'wrong', label: 'Where it comes from', britannica: { passageId: 'B3', quote: 'others, with greater probability, a crystallization from water' }, wikipedia: { passageId: 'W3', quote: 'settled the question in favour of a volcanic origin' }, note: 'The entry backs the water theory. Fieldwork on old volcanoes proved it wrong.' },
    { id: 'b4', kind: 'reworded', verdict: 'correct', label: 'A product of fire', britannica: { passageId: 'B3', quote: 'Some hold it to be a production of fire' }, wikipedia: { passageId: 'W1', quote: 'formed from the rapid cooling of lava' }, note: 'The minority view on the 1797 page is the modern account.' },
    { id: 'b5', kind: 'retained', verdict: 'correct', label: 'Black glass', britannica: { passageId: 'B4', quote: 'melts in a strong fire into a black glass' }, wikipedia: { passageId: 'W4', quote: 'forms a black volcanic glass' }, note: 'The same observation, from the furnace then and the volcano now.' },
    { id: 'b6', kind: 'reworded', verdict: 'partly', label: 'What it is used for', britannica: { passageId: 'B5', quote: 'used by the jewellers as a touchstone for trying gold and silver' }, wikipedia: { passageId: 'W6', quote: 'Crushed basalt is used as aggregate in roads' }, note: 'The uses followed the trades: the jeweller’s touchstone gave way to road building.' },
    { id: 'b7', kind: 'added', verdict: null, label: 'The ocean floor and other planets', britannica: null, wikipedia: { passageId: 'W5', quote: 'Basalt makes up most of the ocean floor' }, note: 'Unknown in 1797: most of the sea floor, and parts of the Moon and Mars, are basalt.' },
  ],
  coverage: [
    { topic: 'Form and columns', britannica: 0.3, wikipedia: 0.2 },
    { topic: 'Where it is found', britannica: 0.2, wikipedia: 0.1 },
    { topic: 'Origin', britannica: 0.25, wikipedia: 0.2 },
    { topic: 'Properties', britannica: 0.1, wikipedia: 0.15 },
    { topic: 'Uses', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Ocean floor and planets', britannica: 0, wikipedia: 0.25 },
  ],
  suggestedQuestions: ['What did the 1797 entry think basalt was made from?', 'Which descriptions of basalt still hold today?'],
  answers: {
    'What did the 1797 entry think basalt was made from?': {
      answer:
        'It reports a split. Some held basalt to be "a production of fire", others, "with greater probability, a crystallization from water" [B3]. Wikipedia says basalt forms from cooling lava [W1], and that field studies of extinct volcanoes settled the 18th-century dispute in favour of a volcanic origin [W3].\n\n' +
        'So the entry backed the losing side, but it recorded the view that turned out right.',
      citations: cite('B3', 'W1', 'W3'),
      grounding: 'supported',
    },
    'Which descriptions of basalt still hold today?': {
      answer:
        "The physical descriptions hold. The columns of several sides [B1] are today's columnar jointing, usually with five or six sides [W2]. The Giant's Causeway is the example in both texts [B2] [W2]. The black glass it melts into [B4] matches Wikipedia's volcanic glass [W4].",
      citations: cite('B1', 'W2', 'B2', 'B4', 'W4'),
      grounding: 'supported',
    },
  },
}

const earthquake: MockTopic = {
  summary: {
    slug: 'earthquake',
    label: 'Earthquake',
    headword: 'EARTHQUAKE',
    edition: 'Third edition',
    year: 1797,
    match: 'strong',
    wikipediaTitle: 'Earthquake',
    area: 'geology',
    teaser: 'The cause is commonly ascribed to subterraneous fires, or to vapours and exhalations which, being rarefied by heat and wanting room, burst forth with violence and shake the ground above them.',
  },
  aliases: ['earthquake', 'earthquakes', 'lisbon'],
  britannica: {
    pageId: 'MOCK-0007',
    headword: 'EARTHQUAKE',
    edition: 'Third edition',
    year: 1797,
    volume: 'Volume 6',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, and miscellaneous literature - Third edition, Volume 6 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `EAR                    [ 214 ]                    EAR

  EARTHQUAKE, a violent agitation or trembling of
ſome conſiderable part of the earth, generally attended
with a terrible noiſe like thunder, and ſometimes with
an eruption of fire, water or wind.
  The cauſe is commonly aſcribed to ſubterraneous fires,
or to vapours and exhalations which, being rarefied by
heat and wanting room, burſt forth with violence and
ſhake the ground above them. Dr Stukeley has ſup-
poſed that earthquakes are owing to electricity, the
ſhock being communicated through the earth as through
other conductors.
  They are moſt frequent in countries abounding with
volcanoes, as Italy, Sicily, and the iſlands of the In-
dian ocean. The moſt dreadful of late years was that
which deſtroyed great part of Liſbon on the firſt of
November 1755, when many thouſands of the inhabi-
tants periſhed.
  EARWIG. See Forficula.`,
    passages: [
      { id: 'B1', section: 'EARTHQUAKE', text: 'EARTHQUAKE, a violent agitation or trembling of some considerable part of the earth, generally attended with a terrible noise like thunder, and sometimes with an eruption of fire, water or wind.' },
      { id: 'B2', section: 'EARTHQUAKE', text: 'The cause is commonly ascribed to subterraneous fires, or to vapours and exhalations which, being rarefied by heat and wanting room, burst forth with violence and shake the ground above them.' },
      { id: 'B3', section: 'EARTHQUAKE', text: 'Dr Stukeley has supposed that earthquakes are owing to electricity, the shock being communicated through the earth as through other conductors.' },
      { id: 'B4', section: 'EARTHQUAKE', text: 'They are most frequent in countries abounding with volcanoes, as Italy, Sicily, and the islands of the Indian ocean.' },
      { id: 'B5', section: 'EARTHQUAKE', text: 'The most dreadful of late years was that which destroyed great part of Lisbon on the first of November 1755, when many thousands of the inhabitants perished.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-earthquake',
    title: 'Earthquake',
    url: wiki('Earthquake'),
    dateModified: '2026-10-04',
    passages: [
      { id: 'W1', section: 'Introduction', text: "An earthquake is the shaking of the Earth's surface caused by a sudden release of energy in the lithosphere that creates seismic waves." },
      { id: 'W2', section: 'Causes', text: 'Most earthquakes happen when rock breaks and slips along a geological fault, as the tectonic plates move against each other. Volcanic activity and human activity, such as mining, cause smaller earthquakes.' },
      { id: 'W3', section: 'Distribution', text: 'Earthquakes concentrate along the boundaries of tectonic plates, such as the Pacific Ring of Fire, where many volcanoes also form.' },
      { id: 'W4', section: 'Measurement', text: 'Seismometers record seismic waves. The size of an earthquake is reported on the moment magnitude scale.' },
      { id: 'W5', section: 'History', text: 'The 1755 Lisbon earthquake, followed by a tsunami and fires, killed tens of thousands of people and is often seen as the start of the scientific study of earthquakes.' },
      { id: 'W6', section: 'Effects', text: 'Earthquakes under the sea can cause tsunamis.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.85,
    rerankScore: 0.92,
    reasons: [
      'Same headword: EARTHQUAKE and Earthquake.',
      'Both name the 1755 Lisbon earthquake.',
      'The article on the Lisbon earthquake scores close behind but covers one event only.',
    ],
  },
  candidates: [
    { title: '1755 Lisbon earthquake', url: wiki('1755 Lisbon earthquake'), embedScore: 0.79, rerankScore: 0.71 },
    { title: 'Seismology', url: wiki('Seismology'), embedScore: 0.74, rerankScore: 0.6 },
    { title: 'Plate tectonics', url: wiki('Plate tectonics'), embedScore: 0.68, rerankScore: 0.5 },
  ],
  alignments: [
    { id: 'e1', kind: 'reworded', verdict: 'correct', label: 'What an earthquake is', britannica: { passageId: 'B1', quote: 'a violent agitation or trembling of some considerable part of the earth' }, wikipedia: { passageId: 'W1', quote: "the shaking of the Earth's surface" }, note: 'The same event in plainer words. Wikipedia adds what travels through the ground: seismic waves.' },
    { id: 'e2', kind: 'revised', verdict: 'wrong', label: 'The cause', britannica: { passageId: 'B2', quote: 'commonly ascribed to subterraneous fires, or to vapours and exhalations' }, wikipedia: { passageId: 'W2', quote: 'rock breaks and slips along a geological fault' }, note: 'Underground fire and trapped vapour gave way to moving plates and breaking rock.' },
    { id: 'e3', kind: 'dropped', verdict: 'wrong', label: 'Earthquakes as electricity', britannica: { passageId: 'B3', quote: 'earthquakes are owing to electricity' }, wikipedia: null, note: 'Stukeley’s electrical theory has no place in the modern account.' },
    { id: 'e4', kind: 'revised', verdict: 'partly', label: 'Near volcanoes', britannica: { passageId: 'B4', quote: 'most frequent in countries abounding with volcanoes' }, wikipedia: { passageId: 'W3', quote: 'where many volcanoes also form' }, note: 'The pattern was right, the reason was not: earthquakes and volcanoes both follow plate boundaries.' },
    { id: 'e5', kind: 'retained', verdict: 'correct', label: 'Lisbon, 1755', britannica: { passageId: 'B5', quote: 'destroyed great part of Lisbon on the first of November 1755' }, wikipedia: { passageId: 'W5', quote: 'The 1755 Lisbon earthquake' }, note: 'Recent news in 1797, and the start of earthquake science today.' },
    { id: 'e6', kind: 'added', verdict: null, label: 'Measuring them', britannica: null, wikipedia: { passageId: 'W4', quote: 'Seismometers record seismic waves' }, note: 'In 1797 there was no way to measure an earthquake, only to describe its damage.' },
  ],
  coverage: [
    { topic: 'What it is', britannica: 0.2, wikipedia: 0.15 },
    { topic: 'Causes', britannica: 0.3, wikipedia: 0.3 },
    { topic: 'Where they happen', britannica: 0.15, wikipedia: 0.2 },
    { topic: 'Notable earthquakes', britannica: 0.2, wikipedia: 0.15 },
    { topic: 'Electrical theory', britannica: 0.15, wikipedia: 0 },
    { topic: 'Measurement', britannica: 0, wikipedia: 0.15 },
    { topic: 'Tsunamis', britannica: 0, wikipedia: 0.05 },
  ],
  suggestedQuestions: ['What did people in 1797 think caused earthquakes?', 'Was the 1797 entry right that earthquakes happen near volcanoes?'],
  answers: {
    'What did people in 1797 think caused earthquakes?': {
      answer:
        'Most blamed "subterraneous fires, or vapours and exhalations" that burst out and shook the ground [B2]. Dr Stukeley proposed electricity instead [B3].\n\n' +
        'Wikipedia explains earthquakes as rock breaking and slipping along faults as tectonic plates move [W2]. Neither 1797 cause survives.',
      citations: cite('B2', 'B3', 'W2'),
      grounding: 'supported',
    },
    'Was the 1797 entry right that earthquakes happen near volcanoes?': {
      answer:
        'Partly. It says earthquakes are most frequent where volcanoes abound [B4], and Wikipedia agrees that both cluster along plate boundaries such as the Ring of Fire [W3].\n\n' +
        'The pattern was right, but the entry took it as cause and effect. Today both are seen as results of moving plates [W2].',
      citations: cite('B4', 'W3', 'W2'),
      grounding: 'supported',
    },
  },
}

const electricity: MockTopic = {
  summary: {
    slug: 'electricity',
    label: 'Electricity',
    headword: 'ELECTRICITY',
    edition: 'Third edition',
    year: 1797,
    match: 'strong',
    wikipediaTitle: 'Electricity',
    area: 'natural-sciences',
    teaser: 'Some philosophers suppose that the nervous fluid itself may be of the same nature with the electric fluid.',
  },
  aliases: ['electricity', 'electric', 'lightning'],
  britannica: {
    pageId: 'MOCK-0008',
    headword: 'ELECTRICITY',
    edition: 'Third edition',
    year: 1797,
    volume: 'Volume 6',
    meta: 'Encyclopaedia Britannica; or, A dictionary of arts, sciences, and miscellaneous literature - Third edition, Volume 6 (mock)',
    imageUrl: null,
    sourceUrl: null,
    rawText: `ELE                    [ 418 ]                    ELE

  ELECTRICITY, the operations of a very ſubtile fluid,
which is excited by the friction of glaſs, amber, ſeal-
ing-wax and other bodies, and cauſes them to attract
and repel light ſubſtances.
  Bodies are divided into electrics, which may be ex-
cited by friction, as glaſs and reſin, and conductors, as
metals and water, which tranſmit the fluid freely.
  Dr Franklin has ſhown that lightning is the ſame with
electricity, by drawing it from the clouds with a kite,
and has taught the method of ſecuring buildings by
pointed rods of iron.
  Electricity has been applied with ſucceſs in medicine,
in palſies, rheumatiſms and other diſorders. Some phi-
loſophers ſuppoſe that the nervous fluid itſelf may be
of the ſame nature with the electric fluid.
  ELECTRUM, amber. See Amber.`,
    passages: [
      { id: 'B1', section: 'ELECTRICITY', text: 'ELECTRICITY, the operations of a very subtile fluid, which is excited by the friction of glass, amber, sealing-wax and other bodies, and causes them to attract and repel light substances.' },
      { id: 'B2', section: 'ELECTRICITY', text: 'Bodies are divided into electrics, which may be excited by friction, as glass and resin, and conductors, as metals and water, which transmit the fluid freely.' },
      { id: 'B3', section: 'ELECTRICITY', text: 'Dr Franklin has shown that lightning is the same with electricity, by drawing it from the clouds with a kite, and has taught the method of securing buildings by pointed rods of iron.' },
      { id: 'B4', section: 'ELECTRICITY', text: 'Electricity has been applied with success in medicine, in palsies, rheumatisms and other disorders.' },
      { id: 'B5', section: 'ELECTRICITY', text: 'Some philosophers suppose that the nervous fluid itself may be of the same nature with the electric fluid.' },
    ],
  },
  wikipedia: {
    identifier: 'mock-electricity',
    title: 'Electricity',
    url: wiki('Electricity'),
    dateModified: '2026-09-27',
    passages: [
      { id: 'W1', section: 'Introduction', text: 'Electricity is the set of physical phenomena associated with the presence and motion of electric charge. In metals, the charge is carried by electrons.' },
      { id: 'W2', section: 'Static electricity', text: 'Rubbing two materials together can transfer electrons from one to the other, leaving both charged. Charged objects attract or repel each other.' },
      { id: 'W3', section: 'Conductors and insulators', text: 'Materials are classed as conductors, such as metals, which let charge flow freely, or insulators, such as glass and rubber, which do not.' },
      { id: 'W4', section: 'Lightning', text: "In 1752 Benjamin Franklin's kite experiment showed that lightning is electrical. Lightning rods, which he invented, still protect buildings." },
      { id: 'W5', section: 'In the body', text: 'Nerve cells send signals as electrical impulses called action potentials.' },
      { id: 'W6', section: 'Medicine', text: 'Electricity is used in medicine in devices such as defibrillators and pacemakers. Early electrotherapy claims for many disorders were mostly unfounded.' },
      { id: 'W7', section: 'Current', text: 'An electric current is a flow of charge. It drives motors, lighting and electronics.' },
    ],
  },
  match: {
    strength: 'strong',
    embedScore: 0.88,
    rerankScore: 0.94,
    reasons: [
      'Same headword: ELECTRICITY and Electricity.',
      "Both cover friction, conductors and Franklin's lightning experiment.",
      'Static electricity scores close behind but leaves out current, nerves and medicine.',
    ],
  },
  candidates: [
    { title: 'Static electricity', url: wiki('Static electricity'), embedScore: 0.83, rerankScore: 0.74 },
    { title: 'Electrostatics', url: wiki('Electrostatics'), embedScore: 0.8, rerankScore: 0.66 },
    { title: 'Lightning rod', url: wiki('Lightning rod'), embedScore: 0.72, rerankScore: 0.55 },
  ],
  alignments: [
    { id: 'x1', kind: 'revised', verdict: 'partly', label: 'What electricity is', britannica: { passageId: 'B1', quote: 'the operations of a very subtile fluid' }, wikipedia: { passageId: 'W1', quote: 'the presence and motion of electric charge' }, note: 'Something does flow, as the fluid theory said, but it is charge carried by particles, not a fluid of its own.' },
    { id: 'x2', kind: 'retained', verdict: 'correct', label: 'Friction', britannica: { passageId: 'B1', quote: 'excited by the friction of glass, amber, sealing-wax and other bodies' }, wikipedia: { passageId: 'W2', quote: 'Rubbing two materials together can transfer electrons' }, note: 'Rubbing still charges things. Today we know it moves electrons.' },
    { id: 'x3', kind: 'retained', verdict: 'correct', label: 'Attract and repel', britannica: { passageId: 'B1', quote: 'causes them to attract and repel light substances' }, wikipedia: { passageId: 'W2', quote: 'Charged objects attract or repel each other' }, note: 'The same observation in both texts.' },
    { id: 'x4', kind: 'reworded', verdict: 'correct', label: 'Electrics and conductors', britannica: { passageId: 'B2', quote: 'electrics, which may be excited by friction, as glass and resin, and conductors, as metals and water' }, wikipedia: { passageId: 'W3', quote: 'conductors, such as metals, which let charge flow freely, or insulators, such as glass' }, note: 'The same division under a new name: the "electrics" are today’s insulators.' },
    { id: 'x5', kind: 'retained', verdict: 'correct', label: 'Franklin and lightning', britannica: { passageId: 'B3', quote: 'Dr Franklin has shown that lightning is the same with electricity' }, wikipedia: { passageId: 'W4', quote: "Benjamin Franklin's kite experiment showed that lightning is electrical" }, note: 'Recent science in 1797, still standing.' },
    { id: 'x6', kind: 'revised', verdict: 'partly', label: 'Electricity in medicine', britannica: { passageId: 'B4', quote: 'applied with success in medicine, in palsies, rheumatisms and other disorders' }, wikipedia: { passageId: 'W6', quote: 'Early electrotherapy claims for many disorders were mostly unfounded' }, note: 'Electricity did find a place in medicine, but not for the palsies and rheumatisms named here.' },
    { id: 'x7', kind: 'reworded', verdict: 'correct', label: 'Nerves are electrical', britannica: { passageId: 'B5', quote: 'the nervous fluid itself may be of the same nature with the electric fluid' }, wikipedia: { passageId: 'W5', quote: 'Nerve cells send signals as electrical impulses' }, note: 'A guess in 1797, confirmed since: nerve signals are electrical.' },
    { id: 'x8', kind: 'added', verdict: null, label: 'Current and its uses', britannica: null, wikipedia: { passageId: 'W7', quote: 'An electric current is a flow of charge' }, note: 'The 1797 entry knows sparks and shocks, not steady current or electric power.' },
  ],
  coverage: [
    { topic: 'What it is', britannica: 0.2, wikipedia: 0.15 },
    { topic: 'Friction and charge', britannica: 0.25, wikipedia: 0.15 },
    { topic: 'Conductors', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Lightning', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Medicine', britannica: 0.15, wikipedia: 0.1 },
    { topic: 'Nerves', britannica: 0.1, wikipedia: 0.1 },
    { topic: 'Current and power', britannica: 0, wikipedia: 0.3 },
  ],
  suggestedQuestions: ['Which of the 1797 claims about electricity turned out right?', 'What did the 1797 entry get wrong about electricity?'],
  answers: {
    'Which of the 1797 claims about electricity turned out right?': {
      answer:
        'Most of them. Friction excites it [B1], as rubbing transfers electrons [W2]. The split into electrics and conductors [B2] survives as insulators and conductors [W3]. Franklin’s proof that lightning is electrical [B3] still stands [W4].\n\n' +
        'Even the guess that the nervous fluid is electrical [B5] is now established: nerve cells signal with electrical impulses [W5].',
      citations: cite('B1', 'W2', 'B2', 'W3', 'B3', 'W4', 'B5', 'W5'),
      grounding: 'supported',
    },
    'What did the 1797 entry get wrong about electricity?': {
      answer:
        'Nothing outright, but two claims are only partly right. It calls electricity "a very subtile fluid" [B1]; today it is charge carried by electrons [W1]. And it says electricity was applied "with success" for palsies and rheumatisms [B4], while Wikipedia calls most early electrotherapy claims unfounded [W6].',
      citations: cite('B1', 'W1', 'B4', 'W6'),
      grounding: 'supported',
    },
  },
}

export const MORE_TOPICS: MockTopic[] = [basalt, earthquake, electricity]
