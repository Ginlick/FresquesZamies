import argparse
from babel.dates import format_date
from jinja2 import Environment, PackageLoader, select_autoescape
import datetime
import dateparser
import json
import arrow
import math
import os
import re
import base64
import requests
import string
import json
from ics import Calendar
import requests
from bs4 import BeautifulSoup
from requests_html import HTMLSession
import sheets

# TODO: replace the tuples in this code with dictionaries using these keys.
KEY_TITLE = "title"
KEY_NAME = "name"
KEY_DATE = "date"
KEY_PLACE = "place"
KEY_URL = "url"
KEY_LANGUAGE = "language"
KEY_CITY = "city"
KEY_LINGUISTIC_REGION = "lregion"
KEY_ORGANIZER = "organizer"

KEY_ELEMENT_ID = "id"
KEY_LANG_EN = "en"
KEY_LANG_FR = "fr"


# Returns a Date object (at midnight) for the given strptime format, or None on failure.
# If the year is not parsed (1900), it's set to the current year.
# https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
def maybeParseDate(date_string, format):
    try:
        dt = datetime.datetime.strptime(date_string, format)
        date = dt.date()
        if date.year == 1900:
            return datetime.date(datetime.datetime.today().year, date.month, date.day)
        return date
    except ValueError:
        return None


# All the scrape_ functions below extract events from various ticketing sytem pages.
# soup: BeautifulSoup object, see https://www.crummy.com/software/BeautifulSoup/bs4/doc/
# Return: array of tuples (title, event name, date, place, url, language)


# BilletWeb
def scrape_BilletWeb(soup, title, language):
    events = []
    for tag in soup.find_all("div", class_="multi_event_container"):
        child = tag.find("div", class_="multi_event_info_empty")
        if child:
            continue  # this container is empty

        child = tag.find("span", class_="multi_event_name_span")
        if not child:
            if not "multi_event_info_empty" in tag["class"]:
                print("BilletWeb name not found? ", tag)
            continue
        name = child.string
        if "FORMATION ANIMATION" in name.upper():
            print("Seems to be a facilitator training, skipping:", name)
            continue

        child = tag.find("div", class_="multi_event_date")
        if child is None:
            print("Date not found?", tag)
            continue
        child2 = child.span
        if child2 is None:
            print("unexpected date:", child)
        date_strings = []  # deal with multi-dates
        for child3 in child2.find_all("span", class_="multi_event_time"):
            date_strings.append(child3.string)
        if len(date_strings) == 0:
            date_strings.append(child2.string)
        dates = []
        for date_string in date_strings:
            # TODO: there has got to be better ways to parse these strings.
            date = dateparser.parse(
                date_string,
                settings=dict(
                    {
                        "DATE_ORDER": "DMY",
                        "REQUIRE_PARTS": ["day", "month"],
                        "SKIP_TOKENS": [
                            "Mon",
                            "Tue",
                            "Wed",
                            "Thu",
                            "Fri",
                            "Sat",
                            "Sun",
                        ],
                    }
                ),
            )
            if not date:
                date = maybeParseDate(date_string, "%a %m/%d")  # ex: Sun 03/25
            if not date:
                date = maybeParseDate(
                    date_string[0:16], "%a %b %d, %Y"
                )  # ex: Sun Mar 03, 2023
            if not date:
                print(
                    "Cannot parse date, discarding event:",
                    date_string,
                    "(" + title + ")",
                )
                continue
            dates.append(date)

        child = tag.find("div", class_="multi_event_place")
        if not child:
            print("Place not found?", tag)
            continue
        place = child.span.string
        if not place:
            continue  # skip online-only events

        child = tag.find("div", class_="multi_event_button")
        if not child:
            print("No button found?", tag)
            continue
        child2 = child.find("a")
        if not child2:
            print("No URL found on button?", tag)
            continue
        url = child2["href"]
        if not url:
            print("Unable to extract URL?", tag)
            continue
        if url.strip() == "#":
            oc = child2["onclick"]
            if not oc:
                print("Unable to extract onclick?", tag)
                continue
            url = oc.split("'")[1]

        real_language = language
        if "Biodiversity Collage" in name:
            real_language = "en"
        for date in dates:
            events.append((title, name, date, place, url, real_language))
    return events


# BilletWeb
def scrape_BilletWebShop(soup, title, url, language):
    events = []
    for tag in soup.find_all("script"):
        if "json_session_data=JSON.parse" in tag.text:
            # This is incredibly fragile
            txt = tag.text
            s = "Base64.decode('"
            z = len(s)
            x = txt.find(s)
            y = txt.find("'))")
            convertsample = txt[x + z : y]

            # convert to a JSON dictionary
            convertbytes = convertsample.encode("ascii")
            convertedbytes = base64.b64decode(convertbytes)
            decodedsample = convertedbytes.decode("ascii")
            json_data = json.loads(decodedsample)

            # extract the events
            for ed in json_data:
                date = datetime.date.fromtimestamp(ed["start_day"])
                place = ed["place"]
                events.append((title, title, date, place, url, language))
    return events


# FresquesZamies
def scrape_FresquesZamies(soup, language):
    events = []
    for tag in soup.find_all("tr", class_="c10")[:3]:
        date_tag = tag.find("span", class_="c1")
        if not date_tag:
            continue
        date = dateparser.parse(date_tag.string).date()

        name_and_link = tag.find("a", class_="c21")
        if not name_and_link:
            continue

        place = "Impact Hub Lausanne"
        if "Marche du Temps Profond" in name_and_link.string:
            place = "en extérieur à Lausanne"

        events.append(
            (
                name_and_link.string,
                name_and_link.string,
                date,
                place,
                name_and_link["href"],
                language,
            )
        )
    return events


# Fresque du Climat: we truncate to the first three per language to avoid drowning out other workshops
def has_class_my3_only(tag):
    if not tag.name == "div":
        return False
    if not tag.has_attr("class"):
        return False
    classes = tag["class"]
    return len(classes) == 1 and classes[0] == "my-3"


def scrape_FresqueDuClimat(soup, title):
    events = []
    tag = soup.find(has_class_my3_only)
    max_count = 3
    for child in tag.find_all("a", class_="text-decoration-none")[:max_count]:
        if child.get("href") == "":
            continue  # no URL, the workshop is fully booked
        url = "https://association.climatefresk.org" + child.get("href")

        child2 = child.find("div", class_="flex-grow-1")
        divs = child2.find_all("div")

        # date, hour, place
        child4 = divs[0].find("small", class_="text-secondary")
        x = child4.text.split("·")
        date_string = x[0].strip()
        date = dateparser.parse(date_string).date()
        place = re.sub(r"\s+", " ", x[2].strip())

        # title, language
        child5 = divs[1]
        name_and_language = child5.text.strip()
        iLanguage = name_and_language.find("(")
        if iLanguage == -1:
            raise Exception("Cannot find language in workshop title: " + name)
        name = name_and_language[:iLanguage].strip()
        language = name_and_language[iLanguage:].strip()
        if language == "(Deutsch)":
            language = "de"
        elif language == "(English)":
            language = "en"
        elif language == "(Français)":
            language = "fr"
        else:
            raise Exception("Language not handled: " + language)

        events.append((title, name, date, place, url, language))
    return events


def is_EventBrite_location(tag):
    return (
        tag.name == "div"
        and tag.has_attr("data-subcontent-key")
        and tag.attrs["data-subcontent-key"] == "location"
    )


# EventBrite
def scrape_EventBrite(soup, title):
    events = []
    for tag in soup.find_all("ul", class_="cc-card-list"):
        for card in tag.find_all("li", class_="cc-card-list__item"):
            child = card.find("h3", class_="eds-event-card-content__title")
            if not child:
                raise Exception("Title element not found")
            inner = child.find("div", class_="eds-is-hidden-accessible")
            if not inner:
                raise Exception("Title text not found")
            name = inner.text

            child = card.find("div", class_="eds-event-card-content__sub-title")
            if not child:
                raise Exception("Subtitle element for date not found")
            date_string = child.text
            date = maybeParseDate(date_string[:11], "%a, %b %d")  # ex: Tue, Mar 21
            if not date:
                print(
                    "Cannot parse date, discarding event:",
                    date_string,
                    "(" + title + ")",
                )
                continue

            child = card.find(is_EventBrite_location)
            if not child:
                if "EN LIGNE" in name.upper():
                    continue
                raise Exception("Location element not found:", card)
            place = child.text

            child = card.find("a", class_="eds-event-card-content__action-link")
            if not child:
                raise Exception("Action link element for URL not found")
            url = child["href"]

            events.append(
                (
                    title,
                    name,
                    date,
                    place,
                    url,
                    "fr",
                )
            )
    return events


# ICAL format
def scrape_ICal(fp, url, title):
    events = []
    c = Calendar(requests.get(url).text)
    for e in c.events:
        if "Formation" in e.name:
            continue  # skip facilitation trainings
        if not e.location:
            continue  # skip online events
        if not "Suisse" in e.location:
            continue
        title = "Atelier GreenDonut"
        if "TEXTILE" in e.name.upper():
            title = "Fresque du Textile"
        elif "DECHETS" in e.name.upper():
            title = "Fresque des Déchets"
        events.append(
            (
                title,
                e.name,
                e.begin.datetime,
                e.location,
                "https://calendar.google.com/calendar/u/0/embed?src=greendonut.info@gmail.com&ctz=Europe/Paris",
                "fr",
            )
        )
    return events


# Given an array of events, filters for Switzerland and appends to each tuple the identified city.
# Input: array of (title, event name, date, place, url, language)
# Output: array of (title, event name, date, place, url, language, city)
def append_city_and_filter_for_switzerland(events, debug):
    normalizer = str.maketrans("ÜÈÂ", "UEA")
    cities = dict()
    for c in (
        "Arosa",
        "Bern",
        "Biel",
        "Bienne",
        "Bulle",
        "Dübendorf",
        "Estavayer",
        "Fribourg",
        "Genève",
        "Gland",
        "Kaufdorf",
        "Lausanne",
        "Le Grand-Saconnex",
        "Morges",
        "Neuchâtel",
        "Nyon",
        "Penthalaz",
        "Pully",
        "Rolle",
        "Sion",
        "St. Gallen",
        "St. Sulpice",
        "Vevey",
        "Zürich",
    ):
        cities[c.upper().translate(normalizer)] = c
    filtered = []
    for event in events:
        name = event[1]
        place = event[3]
        normalized_place = place.upper().translate(normalizer)

        if normalized_place.endswith("BELGIQUE"):
            continue

        city = None
        for normalized_city, c in cities.items():
            if normalized_city in normalized_place and not "FRANCE" in normalized_place:
                city = c
                break

        if not city and "SEV52" in normalized_place:
            city = "Lausanne"

        if not city:
            calendar = event[0]
            if "Climate Fresk" in calendar or "Fresque du Climat" in calendar:
                raise Exception("Missed Swiss city:", place, "(" + name + ")")
            if debug:
                print("Discarding, not in Switzerland:", place, "(" + name + ")")
            continue

        filtered.append(tuple([*list(event), city]))
    return filtered


# Given an array of events, build a dictionary with the cities and a list of events in each.
def group_events_by_city(events):
    # the main cities we care about and where enough events happen.
    # in a future version of this algorithm, we could derive this list from the events themselves.
    cities = ("Bern", "Genève", "Lausanne", "Zürich", "Zurich")

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
    grouped[""] = lone_events

    return grouped


# Refreshes the file at "filename", if at least a day behind "today", with the contents at "url".
def refresh_cache(filename, today, url):
    try:
        ts = os.path.getmtime(filename)
    except OSError:
        ts = 0
    filetime = datetime.datetime.fromtimestamp(ts)
    delta = today - filetime
    if delta.days >= 1:
        print('Refreshing "' + filename + '" from ' + url + ", date was", filetime)

        if url.startswith("https://www.eventbrite.com/"):
            session = HTMLSession()
            r = session.get(url)
            r.html.render()  # this call executes the js in the page
            with open(filename, "w") as f:
                print(r.html.find("ul.cc-card-list", first=True).html, file=f)
        else:
            r = requests.get(url)
            with open(filename, "w") as f:
                print(r.text, file=f)


# write events as JSON
# TODO: replace event tuples in this code with dictionaries to begin with
def write_events_as_json(events):
    ae = []
    t = datetime.time(0, 0)
    for event in events:
        lregion = "Romandie"
        if event[6] in (
            "Arosa",
            "Bern",
            "Dübendorf",
            "Kaufdorf",
            "St. Gallen",
            "Zürich",
        ):
            lregion = "Deutschschweiz"
        elif event[6] in ("Fribourg"):
            lregion = "Sarine / Röstigraben"
        organizer = None
        if event[0] == "Fresque du Climat" or event[0] == "Climate Fresk":
            organizer = "CF"
        if event[3] == "WWF Schweiz, Hohlstrasse 110, 8004 Zürich":
            organizer = "OPF"
        if "Espace de coworking Sev52" in event[3]:
            organizer = "FZC"
        de = {
            KEY_TITLE: event[0],
            KEY_NAME: event[1],
            KEY_DATE: math.floor(datetime.datetime.combine(event[2], t).timestamp()),
            KEY_PLACE: event[3],
            KEY_URL: event[4],
            KEY_LANGUAGE: event[5],
            KEY_CITY: event[6],
            KEY_LINGUISTIC_REGION: lregion,
            KEY_ORGANIZER: organizer,
        }
        ae.append(de)
    return ae


# Language handling
def inject_language_handling(f):
    print("<script>", file=f)
    print(
        "const languageStrings=" + json.dumps(sheets.get_language_strings(), indent=4),
        file=f,
    )
    print(
        """
function changeLanguage(lang, region_set) {
    for (let i in languageStrings) {
        let d = languageStrings.at(i)
        document.getElementById(d.id).innerHTML = d[lang]
    }
    rebuildEventTable(region_set)
}
""",
        file=f,
    )
    print("</script>", file=f)


def main():
    # Parse the command-line flags.
    argParser = argparse.ArgumentParser()
    argParser.add_argument(
        "-c",
        "--cache_dir",
        default="cache",
        help="Directory where the HTML files are cached for 1 day to reduce host load.",
    )
    argParser.add_argument(
        "-a",
        "--about_html",
        default="/dev/null",
        help="Output 'about' HTML file to write, disabled if left empty.",
    )
    argParser.add_argument(
        "-e",
        "--events_js",
        default="/dev/null",
        help="Output 'evemts' JavaScript file to write, disabled if left empty.",
    )
    argParser.add_argument(
        "-m",
        "--main_html",
        default="/dev/null",
        help="Output 'main' HTML file to write, disabled if left empty.",
    )
    argParser.add_argument(
        "-d", "--debug", default=False, help="Whether to output debug information."
    )
    args = argParser.parse_args()

    # Set up the list of calendars we are going to read.
    # Each tuple is (workshop name, calendar URL, language, main site).
    calendars = [
        (
            "Fresque de la Mobilité",
            "https://www.billetweb.fr/multi_event.php?multi=11698",
            "fr",
            "https://fresquedelamobilite.org/",
        ),
        (
            "Fresque Océane",
            "https://www.billetweb.fr/multi_event.php?multi=15247",
            "fr",
            "https://www.fresqueoceane.org/",
        ),
        (
            "Fresque de l'Alimentation",
            "https://www.billetweb.fr/multi_event.php?multi=11155",
            "fr",
            "https://fresquealimentation.org/",
        ),
        (
            "Fresque de la Biodiversité",
            "https://www.billetweb.fr/shop.php?event=biodiversity-collage-zurich-switzerland&color=no&page=1&margin=margin_small",
            "fr",
            "https://www.fresquedelabiodiversite.org/",
        ),
        (
            "Biodiversity Collage",
            "https://www.billetweb.fr/shop.php?event=biodiversity-collage-zurich-switzerland&color=no&page=1&margin=margin_small",
            "en",
            "https://www.fresquedelabiodiversite.org/en.html",
        ),
        (
            "Fresque du Numérique",
            "https://www.billetweb.fr/shop.php?event=suisse-atelier-fresque-du-numerique&color=5190f5&page=1&margin=no_margin",
            "fr",
            "https://www.fresquedunumerique.org/",
        ),
        (
            "Digital Collage",
            "https://www.billetweb.fr/united-kingdom-digital-collage&multi=12991&language=en&color=5190F5&parent=1&language=en&color=5190F5",
            "en",
            "https://digitalcollage.org/",
        ),
        (
            "Digital Collage",
            "https://www.billetweb.fr/digital-collage-dach&multi=12991&language=en&color=5190F5&parent=1&language=en&color=5190F5",
            "de",
            "https://digitalcollage.org/",
        ),
        (
            "Atelier Ogre",
            "https://www.billetweb.fr/multi_event.php?multi=13026",
            "fr",
            "https://atelierogre.org/",
        ),
        (
            "Fresque de l'Eau",
            "https://www.billetweb.fr/multi_event.php?multi=u138110&margin=no_margin",
            "fr",
            "https://www.eaudyssee.org/ateliers-ludiques-eau/fresque-de-leau/",
        ),
        (
            "Fresque de la Construction",
            "https://www.billetweb.fr/multi_event.php?multi=11574",
            "fr",
            "https://www.fresquedelaconstruction.org/",
        ),
        (
            "Fresques Zamies",
            "https://fresqueszamies.ch/",
            "fr",
            "https://fresqueszamies.ch/",
        ),
        # TODO: introduce a priority scheme to fill with FdC if there's nothing else (ex: less than 8)
        # (
        #    "Fresque du Climat",
        #    "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=18",
        #    "fr",
        #    "https://fresqueduclimat.ch/",
        # ),
        (
            "Climate Fresk",
            "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=3",
            "en",
            "https://klimapuzzle.ch/",
        ),
        (
            "Climate Fresk",
            "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=2",
            "de",
            "https://climatefresk.ch/",
        ),
        (
            "L'Affresco del Clima",
            "https://association.climatefresk.org/training_sessions/search_public_wp?utf8=%E2%9C%93&authenticity_token=jVbLQTo8m9BIByCiUa4xBSl6Zp%2FJW0lq7FgFbw7GpIllVKjduCbQ6SzRxkC4FpdQ4vWnLgVXp1jkLj0cK56mGQ%3D%3D&language=fr&tenant_token=36bd2274d3982262c0021755&user_input_autocomplete_address=&locality=&latitude=&longitude=&distance=100&country_filtering=206&categories%5B%5D=ATELIER&email=&commit=Valider&facilitation_languages%5B%5D=22",
            "it",
            "https://climatefresk.ch/",
        ),
        (
            "Fresque des Nouveaux Récits",
            "https://www.billetweb.fr/multi_event.php?&multi=21617&view=list",
            "fr",
            "https://www.fresquedesnouveauxrecits.org/",
        ),
        (
            "Fresque Agri'Alim",
            "https://www.billetweb.fr/multi_event.php?multi=11421",
            "fr",
            "https://fresqueagrialim.org/",
        ),
        (
            "Fresque du Sexisme",
            "https://www.billetweb.fr/multi_event.php?multi=21743&view=list",
            "fr",
            "https://fresque-du-sexisme.org/",
        ),
        # Disabled on 25.11.23: crashes
        # (
        #    "Fresque du Sol",
        #    "https://framagenda.org/remote.php/dav/public-calendars/KwNwGA232xD38CnN/?export",
        #    "fr",
        # ),
        (
            "Green Donut",
            "https://calendar.google.com/calendar/ical/greendonut.info%40gmail.com/public/basic.ics",
            "fr",
            "https://greendonut.org/dechets/",
        ),
        (
            "PSI (Puzzle des Solutions Individuelles Climat)",
            "https://www.billetweb.fr/multi_event.php?multi=21038",
            "fr",
            "https://www.puzzleclimat.org/",
        ),
        # Disabled on 06.12.23: crashes,
        # (
        #    "2tonnes",
        #    "https://www.eventbrite.com/cc/ateliers-grand-public-en-presentiel-hors-france-2157189",
        #    "fr",
        #    "https://www.2tonnes.org/",
        # ),
        (
            "Fresque du Plastique",
            "https://www.eventbrite.fr/o/la-fresque-du-plastique-45763194553",
            "fr",
            "https://fresqueduplastique.fr/",
        ),
        (
            "Marche de l'Humanité (beta)",
            "https://www.billetweb.fr/multi_event.php?multi=26467",
            "fr",
            "Marche de l'Humanité (beta)",
        ),
        (
            "Fresque de la RSE",
            "https://www.billetweb.fr/multi_event.php?&multi=24016",
            "fr",
            "https://fresquedelarse.org/",
        ),
    ]
    calendars.sort(key=lambda c: c[0])  # sort by workshop name

    # Prepare cache.
    if not os.path.exists(args.cache_dir):
        os.mkdir(args.cache_dir)
    today = datetime.datetime.today()

    # Start with events we have manually collected.
    all_events = sheets.get_manual_events()
    print(len(all_events), "added manually:", all_events)

    # Add scraped events.
    for calendar in calendars:
        title = calendar[0]
        url = calendar[1]
        language = calendar[2]

        # load and parse the file
        filename = os.path.join(args.cache_dir, title + "_" + language + ".html")
        refresh_cache(filename, today, url)
        with open(filename) as fp:
            if url.endswith(".ics") or url.startswith("https://framagenda.org/"):
                events = scrape_ICal(fp, url, title)
            else:
                soup = BeautifulSoup(fp, "html.parser")

                # scrape the events depending on the ticketing platform
                if url.startswith("https://www.billetweb.fr/shop.php"):
                    events = scrape_BilletWebShop(soup, title, url, language)
                elif url.startswith("https://www.billetweb.fr/"):
                    events = scrape_BilletWeb(soup, title, language)
                elif url.startswith("https://fresqueszamies.ch/"):
                    events = scrape_FresquesZamies(soup, language)
                elif url.startswith("https://association.climatefresk.org/"):
                    events = scrape_FresqueDuClimat(soup, title)
                elif url.startswith("https://www.eventbrite."):
                    events = scrape_EventBrite(soup, title)
                else:
                    raise Exception("URL not handled: " + url)

        print_url = ""
        if len(events) == 0:
            print_url = "(" + url + ")"
        print(len(events), "scraped from", title, "(" + language + ")", print_url)
        all_events.extend(events)

    count_parsed_events = len(all_events)
    all_events = append_city_and_filter_for_switzerland(all_events, args.debug)
    grouped = group_events_by_city(all_events)

    for event in all_events:
        # event must have an actual Date object
        if not isinstance(event[2], datetime.date):
            raise Exception("Not a date object:", event[2], event)
        # event must have a valid URL
        if not event[4] or not (
            event[4].startswith("http://")
            or event[4].startswith("https://")
            or event[4].startswith("mailto:")
        ):
            raise Exception("Invalid URL in event", event)

    env = Environment(
        loader=PackageLoader("scrape"),
        autoescape=False,  # TODO: replace with select_autoescape()
    )

    with open(args.main_html, "w") as f:
        template = env.get_template("index.html")
        print(
            template.render(
                {
                    "languageStrings": json.dumps(
                        sheets.get_language_strings("MainPage"), indent=4
                    ),
                    "initialDate": format_date(today, "MM/dd/yyyy", locale="en"),
                    "initialTime": str(
                        math.floor(datetime.datetime.timestamp(datetime.datetime.now()))
                    ),
                }
            ),
            file=f,
        )

    with open(args.events_js, "w") as f:
        template = env.get_template("events.js")
        print(
            template.render(
                {
                    "eventsAsJSON": json.dumps(
                        write_events_as_json(all_events), indent=4
                    ),
                }
            ),
            file=f,
        )

    print(
        "Wrote",
        len(all_events),
        "events to",
        args.main_html,
        "after parsing",
        count_parsed_events,
        "events from",
        len(calendars),
        "calendars.",
    )

    with open(args.about_html, "w") as f:
        template = env.get_template("about.html")
        calendarList = []
        for calendar in calendars:
            calendarList.append('<a href="' + calendar[3] + '">' + calendar[0] + "</a>")
        print(
            template.render(
                {
                    "languageStrings": json.dumps(
                        sheets.get_language_strings("AboutPage"), indent=4
                    ),
                    "calendarList": ", ".join(calendarList),
                }
            ),
            file=f,
        )


if __name__ == "__main__":
    main()
