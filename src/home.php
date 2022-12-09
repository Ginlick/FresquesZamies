<?php

 ?>﻿

<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <link rel="icon" href="/favicon.ico">
  <title>Fresques Zamies & Co</title>
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
        width: min(450px, 30%);
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
      .titleCont {
        margin: 250px 0 100px;
      }
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
  <img class="cornerimg" src="/visuals/cornerimg.jpeg" alt="globe" />
  <section class="cont-column">
    <div class="titleCont">
      <h1>Fresques Zamies <span style="color:var(--accentcolor-2)">& Co</span></h1>
      <p class="slogan">chaque mois un nouvel atelier</p>
    </div>
    <h2>Nos Évènements</h2>
    <div class="tableCont">
      <table class="eventsTable">
        <!-- <thead>
          <tr>
            <td>Date</td>
            <td>Description</td>
            <td>Lien</td>
            <td></td>
          </tr>
        </thead> -->
        <tbody>
          <tr>
            <td>Lundi 30 janvier</td>
            <td><a href="">Fresque du Textile</a></td>
          </tr>
          <tr>
            <td>Lundi 30 janvier</td>
            <td><a href="">Fresque du Textile</a></td>
          </tr>
          <tr>
            <td>Lundi 30 janvier</td>
            <td><a href="">Fresque du Textile</a></td>
          </tr>
          <tr>
            <td>Lundi 30 janvier</td>
            <td><a href="">Fresque du Textile</a></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="impactCont">
      <img src="/visuals/impactHubLogo.png" alt="impactHub Lausanne" />
      <p>toujours 18h - 21h30</p>
    </div>

    <p>Pour toute question contacter <a href="mailto:kroq@sunrise.ch" target="_blank">Karine</a> ou <a href="mailto:jeffounet3@gmail.com" target="_blank">Jeffrey</a></p>
  </section>
</body>
</html>

<script>

</script>
