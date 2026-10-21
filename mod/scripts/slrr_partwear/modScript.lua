-- Part wear: load the game-side extension and keep it alive across level loads. It does nothing until the Mods page switches part wear on.
setExtensionUnloadMode('slrr_partwear', 'manual')
extensions.load('slrr_partwear')
