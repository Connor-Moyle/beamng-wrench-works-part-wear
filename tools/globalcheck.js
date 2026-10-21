// Part wear: a check of the Lua files for (1) undefined globals, by context (vehicle files against the car's globals, game-side files against the game's), and (2) the strings one side
// sends to the other: a string sent to a car (send(id, '...'), veh:queueLuaCommand('...')) must not use game-side-only globals (setExtensionUnloadMode: found in the game, it stopped the whole
// command), and a string a car sends to the game (obj:queueGameEngineLua('...')) must not use car-only globals.
//   NODE_PATH=<folder with node_modules/luaparse> node tools/globalcheck.js
const fs = require('fs');
const path = require('path');
const luaparse = require('luaparse');

const STD = 'assert error ipairs pairs next pcall xpcall select setmetatable getmetatable rawget rawset rawequal tonumber tostring type unpack require print math string table os io _G coroutine'.split(' ');
const GE_ONLY = 'setExtensionUnloadMode be getObjectByID getPlayerVehicle scenetree jsonReadFile jsonWriteFile core_vehicle_manager core_camera Engine FS Sim loadJsonMaterialsFile core_environment ui_options deepcopy'.split(' ');
const CAR_ONLY = 'obj electrics wheels powertrain energyStorage particles fire v beamstate sensors ai input'.split(' ');
const GAME = {
  ge: [...GE_ONLY, 'log', 'extensions', 'slrr_settings', 'slrr_partwear', 'carSurfaceFx', 'sl_career', 'sl_fleet', 'career_career', 'career_modules_inventory', 'dumps', 'vec3'],
  vehicle: [...CAR_ONLY, 'log', 'extensions', 'guihooks', 'slrrWear', 'slrrWearProbe', 'slrrWearLook', 'vec3', 'slrr_partwear'],
};

// the words of a string of Lua that are used as variables (not after a dot or colon, not inside a quoted string)
function words(s) {
  const bare = s.replace(/'[^']*'|"[^"]*"/g, '""');
  const out = [];
  const re = /(^|[^.:\w])([A-Za-z_]\w*)/g;
  let m;
  while ((m = re.exec(bare))) out.push(m[2]);
  return out;
}

// problems in a file's source: [{ line, text }]
function check(code, kind) {
  const bad = [];
  const ast = luaparse.parse(code, { luaVersion: 'LuaJIT', locations: true });
  const allowed = new Set([...STD, ...GAME[kind]]);
  const scopes = [new Set()];
  const declared = (n) => scopes.some((s) => s.has(n));
  const sinkOf = (call) => {                                       // the name of the function a call is to
    const b = call.base;
    return b.type === 'Identifier' ? b.name : (b.type === 'MemberExpression' ? b.identifier.name : null);
  };
  function strings(node, out) {                                    // every string literal inside an expression
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach((n) => strings(n, out)); return; }
    if (node.type === 'StringLiteral') { out.push(node.raw.slice(1, -1)); return; }
    for (const k of Object.keys(node)) if (k !== 'type' && k !== 'loc' && k !== 'range') strings(node[k], out);
  }
  function walk(node) {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(walk); return; }
    switch (node.type) {
      case 'LocalStatement':
        node.init.forEach(walk);
        node.variables.forEach((v) => scopes[scopes.length - 1].add(v.name));
        return;
      case 'FunctionDeclaration': {
        if (node.identifier && node.identifier.type === 'Identifier') {
          if (node.isLocal) scopes[scopes.length - 1].add(node.identifier.name); else walk(node.identifier);
        } else if (node.identifier) walk(node.identifier);
        scopes.push(new Set(node.parameters.filter((p) => p.type === 'Identifier').map((p) => p.name)));
        walk(node.body);
        scopes.pop();
        return;
      }
      case 'ForNumericStatement':
        walk(node.start); walk(node.end); walk(node.step);
        scopes.push(new Set([node.variable.name])); walk(node.body); scopes.pop();
        return;
      case 'ForGenericStatement':
        walk(node.iterators);
        scopes.push(new Set(node.variables.map((v) => v.name))); walk(node.body); scopes.pop();
        return;
      case 'DoStatement': case 'WhileStatement': case 'RepeatStatement': case 'IfClause': case 'ElseifClause': case 'ElseClause':
        scopes.push(new Set()); for (const k of Object.keys(node)) if (k !== 'type' && k !== 'loc' && k !== 'range') walk(node[k]); scopes.pop();
        return;
      case 'TableKeyString': walk(node.value); return;
      case 'MemberExpression': walk(node.base); return;
      case 'CallExpression': case 'StringCallExpression': {
        const sink = sinkOf(node);
        const wrongOnes = kind === 'ge' && (sink === 'send' || sink === 'queueLuaCommand') ? GE_ONLY : (kind === 'vehicle' && sink === 'queueGameEngineLua' ? CAR_ONLY : null);
        if (wrongOnes) {
          const lits = [];
          strings(node.arguments, lits);
          for (const s of lits) for (const w of words(s)) if (wrongOnes.includes(w)) bad.push({ line: node.loc.start.line, text: `'${w}' in a string sent to the ${kind === 'ge' ? 'car' : 'game'} exists only on the ${kind === 'ge' ? 'game' : 'car'} side` });
        }
        break;
      }
      case 'Identifier':
        if (!declared(node.name) && !allowed.has(node.name)) bad.push({ line: node.loc.start.line, text: `undefined global '${node.name}'` });
        return;
    }
    for (const k of Object.keys(node)) if (k !== 'type' && k !== 'loc' && k !== 'range') walk(node[k]);
  }
  walk(ast.body);
  return bad;
}
module.exports = { check };

if (require.main === module) {
  const root = process.argv[2] || path.join(__dirname, '..', 'mod', 'lua');
  const files = [];
  (function walk(d) { for (const f of fs.readdirSync(d, { withFileTypes: true })) f.isDirectory() ? walk(path.join(d, f.name)) : f.name.endsWith('.lua') && files.push(path.join(d, f.name)); })(root);
  let n = 0;
  for (const file of files) {
    const kind = file.includes(path.sep + 'vehicle' + path.sep) ? 'vehicle' : (file.includes(path.sep + 'ge' + path.sep) ? 'ge' : 'common');
    if (kind === 'common') continue;                         // the pure rules: no game calls at all, checked by the Python tests
    for (const b of check(fs.readFileSync(file, 'utf8'), kind)) { console.log(`${path.relative(root, file)}:${b.line}: ${b.text}`); n++; }
  }
  console.log(n ? `${n} problem(s)` : `globals ok in ${files.length} files`);
  process.exit(n ? 1 : 0);
}
