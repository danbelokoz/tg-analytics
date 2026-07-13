#!/usr/bin/env python3
"""Скачивает логотипы известных компаний ОДИН РАЗ и кладёт в /logos на нашем домене.

Зачем не в рантайме: сайт обязан открываться в РФ без VPN, браузер должен ходить
только на наш домен (см. PROJECT.md «Доступность в РФ»). Поэтому лого забираем на
сборке отсюда, а фронт отдаёт их со своего же домена с fallback на букву-бейдж.

Источники (в порядке предпочтения):
  1) https://{domain}/apple-touch-icon.png  — обычно чёткие 180×180
  2) https://icons.duckduckgo.com/ip3/{domain}.ico — надёжный fallback (48×48)
Всё нормализуем в PNG (sips). Домены выверены вручную — чтобы не подтянуть чужой лого.

Запуск:  parser/.venv/bin/python parser/fetch_logos.py
"""
import os, sys, ssl, time, subprocess, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT  = os.path.join(ROOT, "logos")
os.makedirs(OUT, exist_ok=True)

# slug (company_slug в вакансии) -> домен. Только те, в ком уверен; остальные
# останутся с буквой-бейджем (мягкая деградация, не ломает вид).
DOMAINS = {
    "openai":"openai.com","anthropic":"anthropic.com","stripe":"stripe.com",
    "databricks":"databricks.com","datadog":"datadoghq.com","snowflake":"snowflake.com",
    "spacex":"spacex.com","airbnb":"airbnb.com","reddit":"reddit.com","figma":"figma.com",
    "notion":"notion.so","coinbase":"coinbase.com","binance":"binance.com","roblox":"roblox.com",
    "canva":"canva.com","twilio":"twilio.com","okta":"okta.com","xai":"x.ai","waymo":"waymo.com",
    "affirm":"affirm.com","elevenlabs":"elevenlabs.io","clickhouse":"clickhouse.com",
    "riot-games":"riotgames.com","wiz":"wiz.io","asana":"asana.com","cohere":"cohere.com",
    "scale-ai":"scale.com","airwallex":"airwallex.com","okx":"okx.com","canonical":"canonical.com",
    "crowdstrike":"crowdstrike.com","nebius":"nebius.com","coreweave":"coreweave.com",
    "discord":"discord.com","revolut":"revolut.com","yandex":"ya.ru","jetbrains":"jetbrains.com",
    "vercel":"vercel.com","supabase":"supabase.com","perplexity":"perplexity.ai",
    "harvey":"harvey.ai","zoox":"zoox.com","alphasense":"alpha-sense.com","legora":"legora.com",
    "saronic":"saronic.com","tenstorrent":"tenstorrent.com","postman":"postman.com",
    "decagon":"decagon.ai","cursor-ai":"cursor.com","robinhood":"robinhood.com",
    "replit":"replit.com","langchain":"langchain.com","cognition":"cognition.ai",
    "synthesia":"synthesia.io","baseten":"baseten.co","proton":"proton.me","clickup":"clickup.com",
    "deepgram":"deepgram.com","suno":"suno.com","lovable":"lovable.dev","mercury":"mercury.com",
    "redis":"redis.io","polymarket":"polymarket.com","writer":"writer.com",
    "cd-projekt-red":"cdprojektred.com","razer":"razer.com","gamma":"gamma.app",
    "arize-ai":"arize.com","fireworks-ai":"fireworks.ai","lambda":"lambda.ai",
    "sardine":"sardine.ai","sandboxaq":"sandboxaq.com","vapi":"vapi.ai","deepl":"deepl.com",
    "linear":"linear.app","naughty-dog":"naughtydog.com","zapier":"zapier.com","tines":"tines.com",
    "krea-ai":"krea.ai","characterai":"character.ai","llamaindex":"llamaindex.ai",
    "photoroom":"photoroom.com","poolside":"poolside.ai","phantom":"phantom.app",
    "google-deepmind":"deepmind.google","descript":"descript.com","hugging-face":"huggingface.co",
    "splice":"splice.com","moonshot-ai":"moonshot.ai","inflection-ai":"inflection.ai",
    "zerotier":"zerotier.com","recraft":"recraft.ai","runway":"runwayml.com",
    "stability-ai":"stability.ai","glean":"glean.com","jasper":"jasper.ai","plata":"plata.mx",
    "rockstargames":"rockstargames.com","larian-studios":"larian.com","proof":"proof.com",
    "whoop":"whoop.com","owner":"owner.com","observeai":"observe.ai","thinking-machines-lab":"thinkingmachines.ai",
    "black-forest-labs":"bfl.ai","boltnew-stackblitz":"bolt.new","quora-poe":"poe.com",
    "wispr-flow":"wisprflow.ai","yazio":"yazio.com","metronome":"metronome.com",
    "verkor":"verkor.com","postscript":"postscript.io","teikametrics":"teikametrics.com",
    "snorkel-ai":"snorkel.ai","candid-health":"joincandidhealth.com","specterops":"specterops.io",
    "the-exploration-company":"exploration.space","tensorwave":"tensorwave.com",
    "periodic-labs":"periodic.com","freed":"getfreed.ai","fay":"faynutrition.com",
    "binalyze":"binalyze.com","polyai":"poly.ai","mind-foundry":"mindfoundry.ai",
    "objective-group":"objective.com","olipop-pbc":"drinkolipop.com","sesame":"sesame.com",
    "kog":"kog.com","k2-space-corporation":"k2space.com",
}

UA = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) logo-bundler/1.0"}
CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE

def get(url, tries=3, timeout=20):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                data=r.read()
                if data and len(data)>200: return data
        except Exception as e:
            last=e; time.sleep(1.2*(i+1))
    return None

def to_png(raw, is_ico, dest):
    tmp=dest+(".ico" if is_ico else ".src.png")
    with open(tmp,"wb") as f: f.write(raw)
    if is_ico:
        r=subprocess.run(["sips","-s","format","png",tmp,"--out",dest],
                         capture_output=True, text=True)
        os.remove(tmp)
        return r.returncode==0 and os.path.exists(dest)
    os.replace(tmp, dest)
    return True

def main():
    ok, fail = [], []
    for slug, dom in sorted(DOMAINS.items()):
        dest=os.path.join(OUT, slug+".png")
        raw=get(f"https://{dom}/apple-touch-icon.png")
        src="apple"
        if not raw:
            raw=get(f"https://icons.duckduckgo.com/ip3/{dom}.ico"); src="ddg"
        if not raw:
            fail.append(slug); print(f"  FAIL {slug:24s} {dom}"); continue
        if to_png(raw, src=="ddg", dest):
            ok.append(slug); print(f"  ok   {slug:24s} {dom:28s} {src} {len(raw)}b")
        else:
            fail.append(slug); print(f"  CONV-FAIL {slug} {dom}")
    print(f"\nИтого: {len(ok)} лого, {len(fail)} без лого")
    print("FAIL:", ", ".join(fail) if fail else "—")
    # манифест для фронта: какие слаги имеют лого
    with open(os.path.join(OUT,"_manifest.txt"),"w") as f:
        f.write("\n".join(sorted(ok)))

if __name__=="__main__":
    main()
