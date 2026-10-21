// the global check itself: a game-side-only call in a string sent to a car fails, a car-only global in a string sent to the game fails, clean code passes.
const { check } = require('./globalcheck.js');
const assert = require('assert');

const bad1 = check("local function send(id, c) end\nsend(7, \"setExtensionUnloadMode('a','manual') extensions.load('a')\")", 'ge');
assert(bad1.length === 1 && /setExtensionUnloadMode/.test(bad1[0].text), JSON.stringify(bad1));
assert(check("local function send(id, c) end\nsend(7, \"extensions.load('a') slrrWear.setSettings({})\")", 'ge').length === 0, 'a clean car command passes');
const bad3 = check("obj:queueGameEngineLua(\"local o = be:getPlayerVehicle(0) obj:getId()\")", 'vehicle');
assert(bad3.length === 1 && /'obj'/.test(bad3[0].text), JSON.stringify(bad3));
assert(check("obj:queueGameEngineLua('if slrr_partwear then slrr_partwear.onReport(5, {}) end')", 'vehicle').length === 0, 'a clean game command passes');
assert(check("local x = undefinedThing(1)", 'vehicle').length === 1, 'an undefined global is found');
console.log('globalcheck test ok');
