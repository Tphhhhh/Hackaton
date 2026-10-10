import { defineConfig } from '../visio-demo/node_modules/@playwright/test/index.mjs';
import { mkdtempSync } from 'node:fs';
const root=new URL('..',import.meta.url).pathname;
const temp=mkdtempSync('/tmp/sentinelle-browser-');
export default defineConfig({testDir:'./tests',testMatch:'**/*.spec.mjs',workers:1,timeout:60000,reporter:'list',outputDir:'test-results',
 use:{baseURL:'http://127.0.0.1:8891',viewport:{width:1440,height:1050},launchOptions:{executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH||undefined}},
 webServer:{command:`${root}/visio/.venv-gpu/bin/python -m sentinelle.tests.browser_server`,cwd:temp,env:{PYTHONPATH:root,USE_BEDROCK:'0'},url:'http://127.0.0.1:8891/',reuseExistingServer:false}});
