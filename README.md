# Woolly

Recursively search for RPMs in Fedora for a given Rust [crate](https://crate.io).

> This tool is merely a starting point for figuring out how much packaging
> effort you will need to bring a rust crate over to Fedora.

## What does "woolly" means?

Nothing. I just liked the name.

## Running the project

```bash
$ uv run rust_rpm_inspector

Analyzing crate: cliclack
Cache directory: /home/r0x0d/.cache/fedora-rust-checker

  Analyzing dependencies ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% • 0:00:15 complete!

  Dependency Summary for 'cliclack'   
╭────────────────────────────┬───────╮
│ Metric                     │ Value │
├────────────────────────────┼───────┤
│ Total dependencies checked │     7 │
│ Packaged in Fedora         │     0 │
│ Missing from Fedora        │     1 │
╰────────────────────────────┴───────╯

Missing crates that need packaging:
  • cliclack

Dependency Tree:
cliclack v0.3.6 • ✗ not packaged
├── console v0.16.1 • ✓ packaged (0.16.1) 
│   ├── encode_unicode v1.0.0 • ✓ packaged (1.0.0) 
│   └── windows-sys v0.61.2 • ✗ not packaged
│       └── windows-link v0.2.1 • ✗ not packaged
├── indicatif v0.18.3 • ✓ packaged (0.16.2, 0.18.0, 0.18.1) 
│   ├── console (already visited)
│   ├── portable-atomic v1.11.1 • ✓ packaged (1.11.1) 
│   ├── unit-prefix v0.5.2 • ✓ packaged (0.5.1) 
│   └── web-time v1.1.0 • ✓ packaged (1.1.0) 
│       ├── js-sys v0.3.82 • ✗ not packaged
│       │   ├── once_cell v1.21.3 • ✓ packaged (1.21.3) 
│       │   └── wasm-bindgen v0.2.105 • ✗ not packaged
│       │       ├── cfg-if v1.0.4 • ✓ packaged (0.1.10, 1.0.3, 1.0.4) 
│       │       ├── once_cell (already visited)
│       │       ├── wasm-bindgen-macro v0.2.105 • ✗ not packaged
│       │       │   ├── quote v1.0.42 • ✓ packaged (0.3.15, 1.0.40, 1.0.41) 
│       │       │   │   └── proc-macro2 v1.0.103 • ✓ packaged (1.0.101, 1.0.103) 
│       │       │   │       └── unicode-ident v1.0.22 • ✓ packaged (1.0.19, 1.0.22) 
│       │       │   └── wasm-bindgen-macro-support v0.2.105 • ✗ not packaged
│       │       │       ├── bumpalo v3.19.0 • ✓ packaged (3.19.0) 
│       │       │       ├── proc-macro2 (already visited)
│       │       │       ├── quote (already visited)
│       │       │       ├── syn v2.0.110 • ✓ packaged (1.0.109, 2.0.106, 2.0.108) 
│       │       │       │   ├── proc-macro2 (already visited)
│       │       │       │   └── unicode-ident (already visited)
│       │       │       └── wasm-bindgen-shared v0.2.105 • ✗ not packaged
│       │       │           └── unicode-ident (already visited)
│       │       └── wasm-bindgen-shared (already visited)
│       └── wasm-bindgen (already visited)
├── once_cell (already visited)
├── strsim v0.11.1 • ✓ packaged (0.10.0, 0.11.1) 
├── textwrap v0.16.2 • ✓ packaged (0.11.0, 0.15.2, 0.16.2) 
└── zeroize v1.8.2 • ✓ packaged (1.8.1, 1.8.2) 
```

Keep in mind that you may not need all of RPMs to be present in Fedora, like
the output above, we have `windows*` crates in the dependency tree, but they
are not used at all.