function changeLanguage(lang, locale, region_set, organizers = null) {
    for (let i in languageStrings) {
        let d = languageStrings.at(i);
        document.getElementById(d.id).innerHTML = d[lang];
    }
    const collection = document.getElementsByClassName("LanguageFlag");
    for (let i = 0; i < collection.length; i++) {
        e = collection[i];
        if (e.id == "Flag-" + lang) {
            e.classList.add("Highlighted");
        } else {
            e.classList.remove("Highlighted");
        }
    }
    rebuildEventTable(region_set, locale, organizers);
}

function updateDateDiff() {
    let inputInitialDate = document.getElementById("initialDate").innerHTML;
    const initialDate = new Date(inputInitialDate);
    let inputInitialTime = document.getElementById("initialTime").innerHTML;
    const initialTime = new Date(parseInt(inputInitialTime) * 1e3);
    var diffTime = Math.abs(nowDate - initialTime);
    var diffMinutes = Math.floor(diffTime / (60 * 1e3));
    if (diffMinutes < 2) {
        t = "à l'instant";
    } else if (diffMinutes < 60) {
        t = "il y a " + diffMinutes + " minutes";
    } else {
        var diffHours = Math.floor(diffMinutes / 60);
        if (diffHours == 1) {
            t = "il y a une heure";
        } else if (diffHours < 24) {
            t = "il y a " + diffHours + " heures";
        } else {
            var diffDays = Math.floor(diffHours / 24);
            if (diffDays == 1) {
                t = "hier";
            } else {
                t = "il y a " + diffDays + " jours";
            }
        }
    }
    document.getElementById("dateDiffHere").innerHTML = t;
}

const nowDate = new Date();

let today = nowDate.setHours(0, 0, 0, 0);

function displayDate(then, date_string) {
    let diff = (then - today) / (1e3 * 60 * 60 * 24);
    if (diff == 0) {
        const d = {
            "de-CH": "heute",
            "en-GB": "today",
            "fr-CH": "aujourd'hui"
        };
        return d[locale];
    } else if (diff == 1) {
        const d = {
            "de-CH": "morgen",
            "en-GB": "tomorrow",
            "fr-CH": "demain"
        };
        return d[locale];
    } else if (diff < 7) {
        let d = {
            "de-CH": `in ${diff} Tage`,
            "en-GB": `in ${diff} days`,
            "fr-CH": `dans ${diff} jours`
        };
        return d[locale];
    } else {
        return date_string;
    }
}

function injectTable(events, locale) {
    let t = "";
    events.sort(function(a, b) {
        return a.date - b.date;
    });
    for (let x in events) {
        let event = events[x];
        workshopSuffix = "";
        if ((event.organizer == "FZC") || (event.organizer == "OPF")) {
            let prefix = "Organized by"
            let organizer = "One Planet Friends"
            if (locale == 'fr-CH') {
                prefix = "Organisé par"
                organizer = "Fresques Zamies & Co"
            } else if (locale == 'de-CH') {
                prefix = "Veranstaltet von"
            }
            workshopSuffix = "<span class='w3-animate-fading OrgOFP'><br>" + prefix + " <b>" + organizer + "</b></span>";
        }
        t += '<tr class="WorkflowRow" onclick="navigate(this, \'' + event.url + "')\">";
        t += "<td>" + event.title + ' <img src="./flags/icons8-' + event.language + '-16.png" alt="' + event.language + '">' + workshopSuffix + "</td>";
        let then = new Date(event.date * 1e3);
        t += '<td class="EventLongDate">' + displayDate(then, then.toLocaleString(locale, {
            dateStyle: "full"
        })) + "</td>";
        t += '<td class="EventShortDate removed">' + then.toLocaleString(locale, {
            dateStyle: "short"
        }) + "</td>";
        t += '<td class="eventLocation">' + event.city + '<span class="EventLocationDetails hidden"><br>' + event.place + "</span></td>";
        t += "</tr>";
    }
    return t;
}

function rebuildEventTable(region_set, locale, organizers) {
    document.getElementById("event_container").innerHTML = "";

    function eventIsInTheFuture(event) {
        return event.date * 1e3 >= today;
    }
    events = events.filter(eventIsInTheFuture);

    function organizerIsAllowed(event) {
        return (organizers == null) || organizers.has(event.organizer);
    }
    events = events.filter(organizerIsAllowed)

    const lregions = new Set();
    for (let x in events) {
        var event = events[x];
        if (region_set.has(event.lregion)) {
            lregions.add(event.lregion);
        }
    }
    ar = Array.from(lregions);
    ar.sort();
    for (let lregion of ar.reverse()) {
        const filtered = events.filter(myFunction);
        function myFunction(event) {
            return (event.lregion == lregion || event.lregion == "Both");
        }
        document.getElementById("event_container").innerHTML += injectTable(filtered, locale);
    }
}

function navigate(t, url) {
    t.style.cursor = "wait";
    window.location = url;
}