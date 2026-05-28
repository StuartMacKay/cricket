#!/usr/bin/env node
/*
Generate a lighthouse report for a web page.

Usage:
    lighthouse.js <url> [--cli-flags-path=<path>]

The report, in JSON format, will be written to stdout.

The optional flags file is a JSON object whose keys are Lighthouse flag
names.  The most commonly used flag is formFactor:

    {"formFactor": "mobile"}   -- mobile emulation (Lighthouse default)
    {"formFactor": "desktop"}  -- desktop emulation, no throttling

When no flags file is supplied Lighthouse runs with its built-in defaults
(mobile emulation with network and CPU throttling).

Note: Lighthouse 13 requires screenEmulation.mobile to be consistent with
formFactor. To avoid validation errors, use the built-in desktop config
preset when formFactor is "desktop" rather than passing formFactor directly
as a flag.

See https://github.com/GoogleChrome/lighthouse/blob/main/docs/emulation.md
*/

import fs from 'fs';
import lighthouse from 'lighthouse';
import desktopConfig from 'lighthouse/core/config/desktop-config.js';
import * as chromeLauncher from 'chrome-launcher';

const url = process.argv[2];

// Parse an optional --cli-flags-path=<file> argument and read the JSON
// contents as Lighthouse flags.
let flags = {};
for (const arg of process.argv.slice(3)) {
    const match = arg.match(/^--cli-flags-path=(.+)$/);
    if (match) {
        flags = JSON.parse(fs.readFileSync(match[1], 'utf8'));
        break;
    }
}

// Extract formFactor before spreading the remaining flags into options.
// Lighthouse 13 validates that screenEmulation.mobile is consistent with
// formFactor; the desktop-config preset sets both correctly, so we use it
// instead of passing formFactor as a raw flag.
const { formFactor, ...remainingFlags } = flags;
const config = formFactor === 'desktop' ? desktopConfig : undefined;

const chrome = await chromeLauncher.launch({
    chromeFlags: ['--headless', '--no-sandbox', '--disable-dev-shm-usage'],
});

const options = {
    logLevel: 'silent',
    output: 'json',
    port: chrome.port,
    ...remainingFlags,
};

const runnerResult = await lighthouse(url, options, config);
console.log(runnerResult.report);
await chrome.kill();
