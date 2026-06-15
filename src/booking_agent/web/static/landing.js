/* Booking Agent — landing-page motion: scroll-reveal, ticket particles,
   an auto-typing sample conversation, and count-up numbers.
   Standalone; does not depend on app.js. Respects reduced-motion. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* 1. Scroll reveal -------------------------------------------------- */
  var revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { threshold: 0.15 });
    revealEls.forEach(function (el) { io.observe(el); });
  } else {
    revealEls.forEach(function (el) { el.classList.add("in"); });
  }

  /* 2. Floating ticket particles in the hero -------------------------- */
  var pc = document.getElementById("particles");
  if (pc && !reduce) {
    var glyphs = ["🎫", "✦", "🎟️", "★", "♪"];
    for (var i = 0; i < 16; i++) {
      var s = document.createElement("span");
      s.className = "particle";
      s.textContent = glyphs[i % glyphs.length];
      s.style.left = (Math.random() * 100) + "%";
      s.style.animationDuration = (10 + Math.random() * 12) + "s";
      s.style.animationDelay = (Math.random() * 10) + "s";
      s.style.fontSize = (0.8 + Math.random() * 1.4) + "rem";
      pc.appendChild(s);
    }
  }

  /* 3. Auto-typing sample conversation -------------------------------- */
  var chat = document.getElementById("demo-chat");
  if (chat) {
    var bubbles = Array.prototype.slice.call(chat.querySelectorAll(".bubble"));
    var typing = document.getElementById("demo-typing");
    var played = false;
    function playDemo() {
      if (played) return; played = true;
      if (reduce) { bubbles.forEach(function (b) { b.classList.add("show"); }); return; }
      var i = 0;
      (function next() {
        if (i >= bubbles.length) { if (typing) typing.classList.remove("show"); return; }
        var b = bubbles[i];
        if (b.classList.contains("bubble--agent") && typing) {
          typing.classList.add("show");
          setTimeout(function () {
            typing.classList.remove("show");
            b.classList.add("show"); i++; setTimeout(next, 700);
          }, 800);
        } else {
          b.classList.add("show"); i++; setTimeout(next, 650);
        }
      })();
    }
    if ("IntersectionObserver" in window) {
      var io2 = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { playDemo(); io2.unobserve(e.target); } });
      }, { threshold: 0.4 });
      io2.observe(chat);
    } else { playDemo(); }
  }

  /* 4. Count-up numbers ----------------------------------------------- */
  function countUp(el) {
    var to = parseFloat(el.getAttribute("data-to")) || 0;
    var dp = (el.getAttribute("data-dp") | 0);
    if (reduce) { el.textContent = to.toFixed(dp); return; }
    var start = null, dur = 1400;
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      el.textContent = (p * to).toFixed(dp);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  var counts = document.querySelectorAll(".count");
  if ("IntersectionObserver" in window) {
    var io3 = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { countUp(e.target); io3.unobserve(e.target); } });
    }, { threshold: 0.6 });
    counts.forEach(function (c) { io3.observe(c); });
  } else { counts.forEach(countUp); }
})();
