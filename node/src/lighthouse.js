#!/usr/bin/env node
/*
Generate a lighthouse report for a web page.

Usage:
    lighthouse.js <url>

The report, in JSON format, will be written to stdout.

See https://github.com/GoogleChrome/lighthouse/blob/main/docs/readme.md
*/

import fs from 'fs';
import lighthouse from 'lighthouse';
import * as chromeLauncher from 'chrome-launcher';

const chrome = await chromeLauncher.launch({chromeFlags: ['--headless']});
const options = {logLevel: 'silent', output: 'json', port: chrome.port};
const runnerResult = await lighthouse(process.argv[2], options);
console.log(runnerResult.report);
await chrome.kill();
