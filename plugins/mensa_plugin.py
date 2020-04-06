import shlex
import requests
import json
import datetime

from matrix_bot_api.mcommand_handler import MCommandHandler
from pprint import pprint
from collections import defaultdict


HELP_DESC = ("!mensa [loc] [today|tomorrow|week] \t\t\t-\tShow dishes in the mensa, loc in {garching,münchen,other,all}\n")


def get_mensadata():
    baseurl = "https://www.devapp.it.tum.de/mensaapp/"
    file = "exportDB.php"
    params = {"mensa_id" : "all"} 
    r = requests.get(baseurl + file, params=params)
    return json.loads(r.text)


def get_city_to_mensen(mensadata):
    """
    return city_name to id and id to city_name dicts
    """
    mensen = mensadata['mensa_mensen']
    c2i = defaultdict(list)
    i2c = defaultdict(lambda: "other")
    for mensa in mensen:
        mensa_id = mensa['id']
        if "münchen" in mensa['anschrift'].lower():
            c2i["münchen"].append(mensa)
            i2c[mensa_id] = "münchen"
        elif "garching" in mensa['anschrift'].lower():
            c2i["garching"].append(mensa)
            i2c[mensa_id] = "garching"
        else:
            c2i["other"].append(mensa)
            i2c[mensa_id] = "other"
    return c2i,i2c  


def complete_word(word, possibilities):
    ws = filter(lambda p: p.startswith(word), possibilities)
    return list(ws)

def parse_args(args):
    """
    return location,datetime.date tuple
    """
    locations = ["münchen", "garching", "other", "all"]
    dates = ["today", "tomorrow", "week"]

    args.pop(0)

    location = "all"

    if args and args[0] not in dates:
        w = args.pop(0).strip().lower().replace("ue", "ü")
        ws = complete_word(w, locations)
        if ws:
            location = ws[0]

    date_string = "today"
    if args:
        w = args.pop(0).strip().lower()
        ws = complete_word(w, dates)
        if ws:
            date_string = ws[0]
    
    td = datetime.date.today()
    if date_string == "today":
        date = td if td.weekday() <= 4 else td + datetime.timedelta(7-td.weekday())
    elif date_string == "tomorrow":
        delta = datetime.timedelta(7-td.weekday() + 1) if td.weekday() >= 4 else datetime.timedelta(1)
        date = td + delta
    else: # week
        date = None # just print out all

    return location,date


async def send_mensadata(plugin, location, date):

    m = get_mensadata()
    c2i,i2c = get_city_to_mensen(m)

    entries = get_mensadata()['mensa_menu']
    if date:
        entries = [entry for entry in entries if entry.get("date") == date.isoformat()]
    if location != "all":
        entries = [entry for entry in entries if i2c[entry.get("mensa_id")] == location]

    entries.sort(key=lambda x:x['mensa_id'])
    entries.sort(key=lambda x:x['date'])
    
    cur_date = ''
    cur_mensa_id = ''
    html = '<pre><code>'
    if entries:
        for entry in entries:
            if entry['date'] != cur_date:
                cur_date = entry['date']
                ndate = datetime.date.fromisoformat(cur_date)
                html += f"\n<h3>{ndate: %A, %B %d}</h3>"
                cur_mensa_id = ''
            if entry['mensa_id'] != cur_mensa_id:
                cur_mensa_id = entry['mensa_id']
                k = [a['name'] for a in m['mensa_mensen'] if a['id'] == cur_mensa_id]
                floc = k[0] if len(k) > 0 else cur_mensa_id
                html += f"\n<h6><u>{floc}<u></h6>\n"

            html += f"""{entry['name']}\n"""
    else:
        html = '''<pre><code>
        No food found :/
        Take a slice of pizza:</br>
                                             ._
                                   ,(  `-.
                                 ,': `.   `.
                               ,` *   `-.   \
                             ,'  ` :+  = `.  `.
                           ,~  (o):  .,   `.  `.
                         ,'  ; :   ,(__) x;`.  ;
                       ,'  :'  itz  ;  ; ; _,-'
                     .'O ; = _' C ; ;'_,_ ;
                   ,;  _;   ` : ;'_,-'   i'
                 ,` `;(_)  0 ; ','       :
               .';6     ; ' ,-'~
             ,' Q  ,& ;',-.'
           ,( :` ; _,-'~  ;
         ,~.`c _','
       .';^_,-' ~
     ,'_;-''
    ,,~
    i'
    :


        </code></pre>'''
    await plugin.send_html(html)



def register_to(plugin):
    async def mensa_callback(room, event):
        args = plugin.extract_args(event)
        location,date = parse_args(args)
        await send_mensadata(plugin, location, date)

    # Add a command handler waiting for the echo command
    mensa_handler = MCommandHandler("mensa", mensa_callback)
    plugin.add_handler(mensa_handler)


# DEBUGGING
if __name__ == "__main__":
    m = get_mensadata()
    print(m.keys())
    #pprint(get_city_to_mensen(m))
