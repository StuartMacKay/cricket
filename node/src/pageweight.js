#!/usr/bin/env node
/**
 * Measure page weight (network transfer size) for a URL using Puppeteer.
 *
 * Usage:
 *   node src/pageweight.js <url> [--device=mobile|desktop]
 *
 * Output: JSON to stdout
 * {
 *   "url": "https://example.com/about/",
 *   "finalUrl": "https://example.com/about/",
 *   "device": "mobile",
 *   "totalTransferSize": 450000,
 *   "totalResourceSize": 1200000,
 *   "resourceCount": 42,
 *   "byType": {
 *     "document":   {"transferSize": 15000, "resourceSize": 42000, "count": 1},
 *     "stylesheet": {"transferSize": 22000, "resourceSize": 85000, "count": 3},
 *     "script":     {"transferSize": 180000, "resourceSize": 600000, "count": 12},
 *     "image":      {"transferSize": 220000, "resourceSize": 460000, "count": 24},
 *     "font":       {"transferSize": 13000, "resourceSize": 13000, "count": 2},
 *     "other":      {"transferSize": 0, "resourceSize": 0, "count": 0}
 *   },
 *   "resources": [
 *     {"url": "...", "type": "script", "mimeType": "application/javascript",
 *      "transferSize": 45000, "resourceSize": 150000}
 *   ]
 * }
 */

import puppeteer from 'puppeteer';

const MOBILE_VIEWPORT = { width: 375, height: 812, deviceScaleFactor: 2, isMobile: true, hasTouch: true };
const DESKTOP_VIEWPORT = { width: 1280, height: 800, deviceScaleFactor: 1, isMobile: false, hasTouch: false };

const MOBILE_UA = 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36';
const DESKTOP_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36';

const RESOURCE_TYPES = ['document', 'stylesheet', 'script', 'image', 'font'];

async function measurePageWeight(url, device = 'mobile') {
  const isDesktop = device === 'desktop';
  const viewport = isDesktop ? DESKTOP_VIEWPORT : MOBILE_VIEWPORT;
  const userAgent = isDesktop ? DESKTOP_UA : MOBILE_UA;

  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
    ],
  });

  try {
    const page = await browser.newPage();
    await page.setViewport(viewport);
    await page.setUserAgent(userAgent);

    // Enable CDP network tracking for accurate transfer sizes
    const client = await page.createCDPSession();
    await client.send('Network.enable');

    const resources = [];
    const responseMap = new Map(); // requestId -> {transferSize, mimeType}

    client.on('Network.responseReceived', (event) => {
      const r = event.response;
      responseMap.set(event.requestId, {
        url: r.url,
        mimeType: r.mimeType || '',
        status: r.status,
        transferSize: r.encodedDataLength || 0,
        resourceSize: r.dataLength || 0,
      });
    });

    client.on('Network.loadingFinished', (event) => {
      const entry = responseMap.get(event.requestId);
      if (entry) {
        entry.transferSize = event.encodedDataLength || entry.transferSize;
        responseMap.set(event.requestId, entry);
      }
    });

    client.on('Network.requestWillBeSent', (event) => {
      // Track resource type from the request initiator
      const entry = responseMap.get(event.requestId) || {};
      entry.resourceType = event.type ? event.type.toLowerCase() : 'other';
      responseMap.set(event.requestId, entry);
    });

    const response = await page.goto(url, {
      waitUntil: 'networkidle2',
      timeout: 60000,
    });

    const finalUrl = page.url();

    // Compile resource list from CDP data
    for (const [requestId, entry] of responseMap.entries()) {
      if (!entry.url) continue;
      const resourceType = RESOURCE_TYPES.includes(entry.resourceType)
        ? entry.resourceType
        : 'other';
      resources.push({
        url: entry.url,
        type: resourceType,
        mimeType: entry.mimeType,
        transferSize: entry.transferSize || 0,
        resourceSize: entry.resourceSize || 0,
      });
    }

    // Aggregate by type
    const byType = {};
    for (const type of [...RESOURCE_TYPES, 'other']) {
      byType[type] = { transferSize: 0, resourceSize: 0, count: 0 };
    }
    let totalTransferSize = 0;
    let totalResourceSize = 0;
    for (const r of resources) {
      const t = byType[r.type] || byType['other'];
      t.transferSize += r.transferSize;
      t.resourceSize += r.resourceSize;
      t.count += 1;
      totalTransferSize += r.transferSize;
      totalResourceSize += r.resourceSize;
    }

    return {
      url,
      finalUrl,
      device,
      totalTransferSize,
      totalResourceSize,
      resourceCount: resources.length,
      byType,
      resources,
    };
  } finally {
    await browser.close();
  }
}

// Parse args
const args = process.argv.slice(2);
const url = args[0];
if (!url) {
  process.stderr.write('Usage: node src/pageweight.js <url> [--device=mobile|desktop]\n');
  process.exit(1);
}

const deviceArg = args.find(a => a.startsWith('--device='));
const device = deviceArg ? deviceArg.split('=')[1] : 'mobile';

measurePageWeight(url, device)
  .then(result => {
    process.stdout.write(JSON.stringify(result));
    process.exit(0);
  })
  .catch(err => {
    process.stderr.write(err.message + '\n');
    process.exit(1);
  });
