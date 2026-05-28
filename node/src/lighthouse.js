#!/usr/bin/env node
/*
Generate a lighthouse report for a web page.

Usage:
    lighthouse.js <url> [--cli-flags-path=<path>] [--html-output-path=<path>]

The JSON report is always written to stdout.  When --html-output-path is
supplied the self-contained HTML report (identical to Chrome's Lighthouse
panel output) is written to that file.

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

// Parse optional arguments:
//   --cli-flags-path=<file>   JSON file of Lighthouse flags
//   --html-output-path=<file> path where the HTML report will be written
let flags = {};
let htmlOutputPath = null;

for (const arg of process.argv.slice(3)) {
    const flagsMatch = arg.match(/^--cli-flags-path=(.+)$/);
    if (flagsMatch) {
        flags = JSON.parse(fs.readFileSync(flagsMatch[1], 'utf8'));
        continue;
    }
    const htmlMatch = arg.match(/^--html-output-path=(.+)$/);
    if (htmlMatch) {
        htmlOutputPath = htmlMatch[1];
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

// Request both JSON and HTML when a HTML output path was given; JSON only
// otherwise.  When multiple formats are requested, runnerResult.report is an
// array whose order matches the output array.
const output = htmlOutputPath ? ['json', 'html'] : 'json';

const options = {
    logLevel: 'silent',
    output,
    port: chrome.port,
    ...remainingFlags,
};

const runnerResult = await lighthouse(url, options, config);

if (htmlOutputPath) {
    const [jsonReport, htmlReport] = runnerResult.report;
    console.log(jsonReport);
    fs.writeFileSync(htmlOutputPath, htmlReport);
} else {
    console.log(runnerResult.report);
}

await chrome.kill();
