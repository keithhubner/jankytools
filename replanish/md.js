/* Tiny self-contained Markdown -> HTML renderer. No dependencies, offline-safe.
 *
 * Covers the subset Claude plans use: fenced code blocks, ATX headings,
 * unordered/ordered lists, blockquotes, horizontal rules, paragraphs, and the
 * inline spans bold / italic / inline-code / links.
 *
 * SAFETY: all source text is HTML-escaped BEFORE any markdown transform, so any
 * literal <script> or HTML in a plan is rendered as text, never executed.
 *
 * Exposes a single global: window.renderMarkdown(text) -> html string.
 */
(function () {
  "use strict";

  function escapeHtml(s) {
    return s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  // Inline spans. Input is already HTML-escaped.
  function renderInline(text) {
    var out = "";
    var i = 0;
    while (i < text.length) {
      // inline code: `...`
      if (text[i] === "`") {
        var end = text.indexOf("`", i + 1);
        if (end !== -1) {
          out += "<code>" + text.slice(i + 1, end) + "</code>";
          i = end + 1;
          continue;
        }
      }
      // links: [label](url)
      if (text[i] === "[") {
        var m = /^\[([^\]]*)\]\(([^)\s]+)\)/.exec(text.slice(i));
        if (m) {
          var url = m[2];
          // Only allow safe-ish URL schemes to avoid javascript: links.
          var safe = /^(https?:|mailto:|\/|#|\.\/|\.\.\/)/i.test(url);
          if (safe) {
            out += '<a href="' + url + '" target="_blank" rel="noopener noreferrer">'
                 + renderInline(m[1]) + "</a>";
          } else {
            out += escapeHtml(m[0]);
          }
          i += m[0].length;
          continue;
        }
      }
      // bold: **...**
      if (text.startsWith("**", i)) {
        var b = text.indexOf("**", i + 2);
        if (b !== -1) {
          out += "<strong>" + renderInline(text.slice(i + 2, b)) + "</strong>";
          i = b + 2;
          continue;
        }
      }
      // italic: *...* (single star, not part of **)
      if (text[i] === "*") {
        var it = text.indexOf("*", i + 1);
        if (it !== -1) {
          out += "<em>" + renderInline(text.slice(i + 1, it)) + "</em>";
          i = it + 1;
          continue;
        }
      }
      out += text[i];
      i++;
    }
    return out;
  }

  function renderMarkdown(src) {
    if (src == null) return "";
    var escaped = escapeHtml(String(src).replace(/\r\n?/g, "\n"));
    var lines = escaped.split("\n");

    var html = [];
    var i = 0;
    var listType = null; // "ul" | "ol" | null

    function closeList() {
      if (listType) {
        html.push("</" + listType + ">");
        listType = null;
      }
    }

    while (i < lines.length) {
      var line = lines[i];

      // fenced code block: ``` ... ```
      var fence = /^\s*```(.*)$/.exec(line);
      if (fence) {
        closeList();
        var code = [];
        i++;
        while (i < lines.length && !/^\s*```\s*$/.test(lines[i])) {
          code.push(lines[i]);
          i++;
        }
        i++; // skip closing fence (or run off the end)
        html.push("<pre><code>" + code.join("\n") + "</code></pre>");
        continue;
      }

      // blank line
      if (/^\s*$/.test(line)) {
        closeList();
        i++;
        continue;
      }

      // horizontal rule
      if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
        closeList();
        html.push("<hr>");
        i++;
        continue;
      }

      // heading
      var h = /^(#{1,6})\s+(.*)$/.exec(line);
      if (h) {
        closeList();
        var level = h[1].length;
        html.push("<h" + level + ">" + renderInline(h[2].trim()) + "</h" + level + ">");
        i++;
        continue;
      }

      // blockquote (one level)
      if (/^\s*&gt;\s?/.test(line)) {
        closeList();
        var quote = [];
        while (i < lines.length && /^\s*&gt;\s?/.test(lines[i])) {
          quote.push(lines[i].replace(/^\s*&gt;\s?/, ""));
          i++;
        }
        html.push("<blockquote>" + renderInline(quote.join(" ")) + "</blockquote>");
        continue;
      }

      // unordered list item
      var ul = /^\s*[-*+]\s+(.*)$/.exec(line);
      if (ul) {
        if (listType !== "ul") { closeList(); html.push("<ul>"); listType = "ul"; }
        html.push("<li>" + renderInline(ul[1]) + "</li>");
        i++;
        continue;
      }

      // ordered list item
      var ol = /^\s*\d+[.)]\s+(.*)$/.exec(line);
      if (ol) {
        if (listType !== "ol") { closeList(); html.push("<ol>"); listType = "ol"; }
        html.push("<li>" + renderInline(ol[1]) + "</li>");
        i++;
        continue;
      }

      // paragraph: gather consecutive plain lines
      closeList();
      var para = [];
      while (i < lines.length && !/^\s*$/.test(lines[i])
             && !/^\s*```/.test(lines[i])
             && !/^(#{1,6})\s+/.test(lines[i])
             && !/^\s*[-*+]\s+/.test(lines[i])
             && !/^\s*\d+[.)]\s+/.test(lines[i])
             && !/^\s*&gt;\s?/.test(lines[i])
             && !/^\s*([-*_])(\s*\1){2,}\s*$/.test(lines[i])) {
        para.push(lines[i].trim());
        i++;
      }
      html.push("<p>" + renderInline(para.join(" ")) + "</p>");
    }

    closeList();
    return html.join("\n");
  }

  window.renderMarkdown = renderMarkdown;
})();
