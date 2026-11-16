import {chromium} from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:2});
try{
 await page.goto(pathToFileURL(path.join(root,'production/storyboard.html')).href);
 await page.evaluate(()=>document.fonts.ready);
 const scenes=JSON.parse(await fs.readFile(path.join(root,'production/story.json')));
 for(const s of scenes){await page.evaluate(id=>{for(const el of document.querySelectorAll('.slide'))el.style.display=el.id===id?'block':'none';window.scrollTo(0,0)},s.id);await page.waitForTimeout(150);await page.screenshot({path:path.join(root,'screenshots',s.id+'.png')});console.log(s.id)}
}finally{await browser.close()}
