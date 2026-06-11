#!/usr/bin/env node
/**
 * Node 原生 HTTP 调用 WPS 58890（不依赖浏览器 SDK）。
 */
'use strict';

const http = require('http');
const { randomUUID } = require('crypto');

const BASE = process.env.WPS_HTTP_BASE || 'http://127.0.0.1:58890';
const ADDIN = process.env.WPS_ADDIN_NAME || 'myteam-wps-deck';
const SERVER_ID = process.env.WPS_SERVER_ID || randomUUID();

function b64(s) {
  return Buffer.from(String(s), 'utf8').toString('base64');
}

function post(path, body, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const url = new URL(path, BASE);
    const data = typeof body === 'string' ? body : JSON.stringify(body);
    const req = http.request(
      {
        hostname: url.hostname,
        port: url.port || 58890,
        path: url.pathname,
        method: 'POST',
        headers: { 'Content-Type': 'text/plain', 'Content-Length': Buffer.byteLength(data) },
        timeout: timeoutMs,
      },
      (res) => {
        let chunks = '';
        res.on('data', (c) => { chunks += c; });
        res.on('end', () => resolve({ status: res.statusCode, body: chunks }));
      },
    );
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(data);
    req.end();
  });
}

async function health() {
  try {
    const v = await post('/version', { serverId: SERVER_ID }, 3000);
    const r = await post('/isRunning', { app: 'wpp', serverId: SERVER_ID }, 3000);
    return {
      ok: v.status === 200,
      version: v.body,
      running: r.body,
      base: BASE,
    };
  } catch (e) {
    return { ok: false, error: e.message, base: BASE };
  }
}

async function invoke(func, param) {
  const cmdId = randomUUID();
  const paramStr = JSON.stringify(param);
  const rspUrl = `${BASE}/transferEcho/runParams`;
  const info = `${paramStr});var xhr=new XMLHttpRequest();xhr.open('POST','${rspUrl}');xhr.send(JSON.stringify({id:'${cmdId}',response:res}));void(0`;
  const startInfo = {
    name: ADDIN,
    function: `var res = ${func}`,
    info,
    showToFront: true,
    jsPluginsXml: '',
  };
  const data = `ksowebstartupwpp://${b64(JSON.stringify(startInfo))}`;
  const wrapper = {
    id: cmdId,
    app: 'wpp',
    data,
    serverId: SERVER_ID,
    mode: false,
    timeout: 120000,
  };
  const res = await post('/transfer/runParams', JSON.stringify(wrapper), 120000);
  return { status: res.status, body: res.body, cmdId };
}

async function main() {
  const cmd = process.argv[2];
  if (!cmd || cmd === 'health') {
    const h = await health();
    console.log(JSON.stringify(h, null, 2));
    process.exit(h.ok ? 0 : 1);
  }
  const param = JSON.parse(process.argv[3] || '{}');
  const out = await invoke(cmd, param);
  console.log(JSON.stringify(out, null, 2));
  process.exit(out.status === 200 ? 0 : 1);
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: e.message }));
  process.exit(1);
});
