import argparse
from babel.dates import format_date, format_datetime, format_time
from datetime import datetime
import os
import re
import requests
import string
from bs4 import BeautifulSoup


# All the scrape_ functions below extract events from various ticketing sytem pages.
# soup: BeautifulSoup object, see https://www.crummy.com/software/BeautifulSoup/bs4/doc/
# Return: array of tuples (title, event name, date, place, url, language)

# BilletWeb
def scrape_BilletWeb(soup, title, language):
    events = []
    for tag in soup.find_all('div', class_='multi_event_info'):
        child = tag.find('div', class_='multi_event_place')
        if not child:
                continue  # skip online-only events
        child2 = child.find('span', class_='title searchable')
        if not child2:
                continue  # skip online-only events

        child = tag.find('span', class_='multi_event_name_span')
        if not child:
                continue
        name = child.string

        child = tag.find('div', class_='multi_event_date')
        if not child:
                continue
        date = child.string

        child = tag.parent.find('div', class_='multi_event_button')
        if not child:
                print('BUTTON NOT FOUND, skipping for event ', child2.string)
                continue
        child3 = child.find('a', class_='custom_color_block')
        if not child3:
                print('BLOCK NOT FOUND, skipping for event ', child2.string)
                continue
        if child3.has_attr('onclick'):
                m = re.match(r".*window.open.'(http.+?)'", child3['onclick'])
                if not m:
                        print('URL NOT FOUND, skipping for event ', child2.string)
                        continue
                url = m.group(1)
        else:
                url = child3['href']

        events.append((name, date, child2.string, url, language))
    return map(lambda t: tuple([title, *list(t)]), events)


# FresquesZamies
def scrape_FresquesZamies(soup, language):
    events = []
    for tag in soup.find_all('tr', class_='c10')[:3]:
        date = tag.find('span', class_='c1')
        if not date:
                continue

        name_and_link = tag.find('a', class_='c21')
        if not name_and_link:
                continue

        events.append((name_and_link.string, name_and_link.string, date.string, 'Impact Hub Lausanne', name_and_link['href'], language))
    return events


# Fresque du Climat: we'll truncate to only the first three per language
def has_class_my3_only(tag):
    if not tag.name == 'div':
        return False
    if not tag.has_attr('class'):
        return False
    classes = tag['class']
    return len(classes) == 1 and classes[0] == 'my-3'


def scrape_FresqueDuClimat(soup, title):
    events = []
    tag = soup.find(has_class_my3_only)
    for child in tag.find_all('a', class_='text-decoration-none')[:10]:
        url = 'https://association.climatefresk.org' + child.get('href')
        child2 = child.find('div', class_='flex-grow-1')
        divs = child2.find_all('div')

        # date, hour, place
        child4 = divs[0].find('small', class_='text-secondary')
        x = child4.text.split('·')
        date = x[0].strip()
        place = re.sub(r'\s+', ' ', x[2].strip())

        # title, language
        child5 = divs[1]
        spans = child5.find_all('span')
        name = spans[0].text
        language = spans[1].text
        if language == '(Deutsch)':
            language = 'de'
        elif language == '(English)':
            language = 'en'
        elif language == '(Français)':
            language = 'fr'
        else:
            raise Exception('Language not handled: ' + language)

        #print('LANG:', spans[1].text)
        events.append((title, name, date, place, url, language))
    return events


# appends the given item to each tuple in the given array
#def append_to_each_tuple(tuples, item):
#    return map(lambda t: tuple([*list(t), item]), tuples)


# Given an array of events, filters for Switzerland and appends to each tuple the identified city.
# Input: array of (title, event name, date, place, url, language)
# Output: array of (title, event name, date, place, url, language, city)
def append_city_and_filter_for_switzerland(events, debug):
    # in a future version of this algorithm, we could derive this list from the events themselves.
    cities = ('Bern', 'Bienne', 'Fribourg', 'Genève', 'Gland', 'Lausanne', 'Sion', 'Zürich')
    filtered = []
    for event in events:
        name = event[1]
        place = event[3]
        city = None
        for c in cities:
            if c in place:
                city = c
                break

        if city is None:
            if 'Fresque du Climat' in name:
                raise Exception('Missed Swiss city: ' + place)
            if debug:
                print('Discarding, not in Switzerland: ', place)
            continue

        filtered.append(tuple([*list(event), city]))
    return filtered


# Given an array of events, build a dictionary with the cities and a list of events in each.
def group_events_by_city(events):
    # the main cities we care about and where enough events happen.
    # in a future version of this algorithm, we could derive this list from the events themselves.
    cities = ('Bern', 'Troulala', 'Genève', 'Lausanne', 'Zürich')

    # fill the dictionary
    grouped = dict()
    for event in events:
        city = event[6]
        if not city in grouped:
            grouped[city] = []
        grouped[city].append(event)

    # move all items that are in a single city, to a common empty key ''
    cities_to_delete = []
    lone_events = []
    for city, events in grouped.items():
        if len(events) < 2:
            cities_to_delete.append(city)
            lone_events.extend(events)
    for city in cities_to_delete:
        del grouped[city]
    grouped[''] = lone_events

    return grouped


# Adds a HTML table row (5 columns) for each event, as long as it appears to be in Switzerland.
# events: input array of tuples (workshop name, event name, date, place, url, language)
# f: file to write to
# debug: boolean, where to emit debug messages
def inject_events(events, f, debug):
    print('''
    <div class="tableCont">
        <table class="eventsTable">
        <thead>
            <tr>
            <td>Atelier</td>
            <td>Date</td>
            <td>Événement</td>
            <td>Lieu</td>
            <td>Lien</td>
            </tr>
        </thead>
        <tbody>
''', file=f)

    for event in events:
        print('<tr>', file=f)
        print('<td>', event[0], '<img src="flags/icons8-' + event[5]+ '-16.png" alt="' + event[5]+ '"/></td>', file=f)
        print('<td>', event[2], '</td>', file=f)
        print('<td>', event[1], '</td>', file=f)
        print('<td>', event[3], '</td>', file=f)
        print('<td><a href="', event[4], '">Billeterie</a></td>', file=f)
        print('</tr>', file=f)

    print('''
        </tbody>
        </table>
    </div>
''', file=f)


# Add a HTML section for a given city
def inject_city(city, events, f, debug):
    if len(events) > 0:
        print('<h2>', city, '</h2>', file=f)
        inject_events(events, f, debug)


# Refreshes the file at "filename", if at least a day behind "today", with the contents at "url".
def refresh_cache(filename, today, url):
    try:
        ts = os.path.getmtime(filename)
    except OSError:
        ts = 0
    filetime = datetime.fromtimestamp(ts)
    delta = today - filetime
    if delta.days >= 1:
        print('Refreshing "' + filename + '" from ' + url + ', date was', filetime)
        r = requests.get(url)
        with open(filename, 'w') as f:
            print(r.text, file=f)


# Main code starts here

# Parse the command-line flags.
argParser = argparse.ArgumentParser()
argParser.add_argument('-c', '--cache_dir', default='cache', help='Directory where the HTML files are cached for 1 day to reduce host load.')
argParser.add_argument('-o', '--output_html', default='/dev/null', help='Output HTML file to write, disabled if left empty.')
argParser.add_argument('-d', '--debug', default=False, help='Whether to output debug information.')
args = argParser.parse_args()

# Set up the list of calendars we are going to read.
# Each tuple is (workshop name, calendar URL).
calendars = [(
    'Fresque de la Mobilité',
    'https://www.billetweb.fr/multi_event.php?multi=11698',
    'fr',
), (
    'Fresque Océane',
    'https://www.billetweb.fr/multi_event.php?multi=15247',
    'fr',
), (
    "Fresque de l'Alimentation",
    'https://www.billetweb.fr/multi_event.php?multi=11155',
    'fr',
), (
    'Fresque de la Biodiversité',
    'https://www.billetweb.fr/multi_event.php?multi=13119',
    'fr',
), (
    'Fresque du Numérique',
    'https://www.billetweb.fr/multi_event.php?multi=11442',
    'FR',
), (
    'Atelier Ogre',
    'https://www.billetweb.fr/multi_event.php?multi=13026',
    'fr',
), (
    'Digital Collage',
    'https://www.billetweb.fr/multi_event.php?multi=12991',
    'en',
), (
    "Fresque de l'Eau",
    'https://www.billetweb.fr/multi_event.php?user=138110',
    'fr',
), (
    'Fresque de la Construction',
    'https://www.billetweb.fr/multi_event.php?multi=11574',
    'fr',
), (
    'Fresques Zamies',
    'https://fresqueszamies.ch/',
    'fr',
), (
    'Fresque du Climat',
    'https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&language=fr&tenant_token=36bd2274d3982262c0021755&country_filtering=206&user_input_autocomplete_address=&locality=&distance=100&show_atelier=true&commit=Valider',
    'all',
), (
    'Fresque des Nouveaux Récits',
    'https://www.billetweb.fr/multi_event.php?&multi=21617&view=list',
    'fr',
), (
    "Fresque Agri'Alim",
    'https://www.billetweb.fr/multi_event.php?multi=11421',
    'fr',
), (
    'Fresque du Sexisme',
    'https://www.billetweb.fr/multi_event.php?multi=21743&view=list',
    'fr',
), (
    'PSI (Puzzle des Solutions Individuelles Climat)',
    'https://www.billetweb.fr/multi_event.php?multi=21038',
    'fr',
)]
calendars.sort(key=lambda c: c[0])  # sort by workshop name

# Inject extra events we are aware of.
#inject_events([
#        ('2tonnes', '2tonnes World', '12 janvier 2023', 'Impact Hub Lausanne', 'https://my.weezevent.com/atelier-2tonnes-a-lausanne'),
#    ], f, args.debug)

# Prepare cache.
if not os.path.exists(args.cache_dir):
    os.mkdir(args.cache_dir)
today = datetime.today()

all_events = []
for calendar in calendars:
    title = calendar[0]
    url = calendar[1]
    language = calendar[2]

    # load and parse the file
    filename = os.path.join(args.cache_dir, title + '_' + language + '.html')
    refresh_cache(filename, today, url)
    with open(filename) as fp:
        soup = BeautifulSoup(fp, 'html.parser')

    # scrape the events depending on the ticketing platform
    if url.startswith('https://www.billetweb.fr/'):
        events = scrape_BilletWeb(soup, title, language)
    elif url.startswith('https://fresqueszamies.ch/'):
        events = scrape_FresquesZamies(soup, language)
    elif url.startswith('https://association.climatefresk.org/'):
        events = scrape_FresqueDuClimat(soup, title)
    else:
        raise Exception('URL not handled: ' + url)

    all_events.extend(events)

count_parsed_events = len(all_events)
all_events = append_city_and_filter_for_switzerland(all_events, args.debug)
grouped = group_events_by_city(all_events)

# TODO: replace with Mako templates or similar.
with open(args.output_html, 'w') as f:
    print('''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <link rel="icon" href="/favicon.ico">
    <title>Ateliers zamis en Suisse</title>
    <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600&family=Hanken+Grotesk:wght@300;400;500&display=swap" rel="stylesheet">

    <style>
    :root {
        --accentcolor-1: #7ea656;
        --accentcolor-2: #820001;
        --accentcolor-1-light: #cedebf;
        --accentcolor-2-light: #e4c5c5;
        --fontfam-headings: "Hanken Grotesk", Arial, sans-serif;
        --fontfam-text: "Open Sans", Arial, sans-serif;
    }
        .cornerimg {
        position: fixed;
        top:0;
        right:0;
        width: min(45px, 20%);
        z-index: -1;
        }
        h1, h2 {
        font-family:var(--fontfam-headings);
        }
        h1 {
        font-size: 40px;
        }
        h2 {
        font-size: 30px;
        }
        p {
        font-family: var(--fontfam-headings);
        color: #323331;
        font-size:18px;
        }
        a {
        color: var(--accentcolor-2);
        transition: .2s ease;
        }
        a:hover {
        color: var(--accentcolor-1);
        }
        #.titleCont {
        #margin: 250px 0 100px;
        #}
        .titleCont h1 {
        color: var(--accentcolor-1);
        font-size: 40px;
        }
        .slogan {
        font-size: 22px;
        }
        .cont-column {
        width: min(100%, 1000px);
        margin:auto;
        }
        .tableCont {
        border: 1px solid #ddd;
        border-radius: 5px;
        }
        .eventsTable {
        border-collapse: collapse;
        width: 100%;
        }
        .eventsTable td {
        padding: 8px;
        font-family: var(--fontfam-text);
        }
        .eventsTable tr {
        transition: .3s ease;
        }
        .eventsTable tr:nth-child(even) {background-color: var(--accentcolor-1-light);}

        .impactCont {
        width: 20%;
        margin:50px auto;
        text-align: center;
        }
        .impactCont img {
        width: 100%;
        }
    </style>
</head>
<body>
    <img class="cornerimg" src="images/image1.jpg" alt="globe" />
    <section class="cont-column">
    <div class="titleCont">
        <h1>Ateliers zamis en Suisse</h1>
        <p>Cette page répertorie les ateliers en présentiel en Suisse prévus prochainement.</p>
    </div>
''', file=f)

    #inject_events(all_events, f, args.debug)
    for city in sorted(grouped):
        if city != '':
            inject_city(city, grouped[city], f, args.debug)
    inject_city('Ailleurs', grouped[''], f, args.debug)

    print('''
    <p>Calendrier lus, entre autres:<ul>
''', file=f)
    for calendar in calendars:
        print('<li><a href="' + calendar[1] + '">', calendar[0], '</a></li>', file=f)
    print('''
    </ul></p>
    <p>Pour une liste encore plus large d'ateliers existants, voir <a href="https://fresqueduclimat.org/wiki/index.php">la liste des fresques amies</a>.</p>
    <p>Pour toute question, suggestion ou bug (par exemple, un lien est cassé, ou un événement en Suisse dans un des calendriers n'est pas répertorié sur cette page), merci de contacter <a href="mailto:jeffrey@theshifters.ch" target="_blank">jeffrey@theshifters.ch</a>.</p>
    <p>Les icônes du <a target="_blank" href="https://icons8.com/icon/u5e279g2v-R8/france">drapeau de France</a> et autres pays sont mis à disposition par <a target="_blank" href="https://icons8.com">Icons8</a>.</p>
''', file=f)
    print('<p>Dernière mise à jour: ' + format_date(today, "dd MMMM yyyy", locale='fr') + '.</p>', file=f)
    print('''
    </section>
</body>
</html>
''', file=f)

print('Wrote', len(all_events), 'events to', args.output_html, 'after parsing', count_parsed_events, 'events from', len(calendars), 'calendars.')