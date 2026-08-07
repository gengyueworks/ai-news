/* AI News 知识卡片浮层 — 精简版
 * 运行时注入：扫描正文 → 标注术语 → 点击显示精简浮层
 * 复用 ai-dictionary.json，只显示 definition_short + why_it_matters
 *
 * 用法：
 *   <link rel="stylesheet" href="glossary.css">
 *   <script src="glossary.js" data-dict="ai-dictionary.json"></script>
 *   或内联词典数据：window.__AI_DICT = [...]; <script src="glossary.js"></script>
 */
(function () {
  'use strict';

  // ====== 配置 ======
  var SCAN_SELECTORS = '.news-body, .intro-text, .news-title, .quote-text';
  var MIN_TERM_LEN = 3;       // 最短术语长度（英文）
  var MIN_TERM_LEN_ZH = 2;    // 中文术语最短长度
  var MAX_TERMS_PER_PAGE = 80; // 单页最多标注数（避免性能问题）
  var MAX_ANNOTATIONS_PER_TERM = 2; // 每个术语最多标注次数（首次 + 末次）

  // 太基础的词，不标注（避免噪音）
  var BLACKLIST = new Set([
    'AI', 'API', 'GPT', 'LLM', 'GPU', 'CPU', 'URL', 'HTML', 'CSS', 'JS',
    'CEO', 'CTO', 'CFO', 'COO', 'PR', 'HR', 'IT', 'IP', 'TV', 'App',
    'The', 'And', 'For', 'But', 'Not', 'Are', 'Was', 'Has', 'Had',
    'New', 'Old', 'Big', 'Top', 'All', 'One', 'Two', 'Day', 'Year',
    'Open', 'Close', 'Start', 'End', 'High', 'Low', 'Fast', 'Slow',
    'Q1', 'Q2', 'Q3', 'Q4', 'US', 'UK', 'EU', 'CN', 'USA', 'NASA'
  ]);

  // ====== 状态 ======
  var dict = [];
  var dictByTerm = {};      // term -> entry（小写）
  var dictByAlias = {};    // alias -> entry（小写）
  var popover = null;
  var activeTrigger = null;

  // 在脚本执行时（非 DOMContentLoaded 回调里）立即保存 script 引用
  // 否则 document.currentScript 在 init() 里会变成 null
  var _script = document.currentScript;
  var _dictUrl = _script && _script.getAttribute('data-dict');

  // ====== 初始化 ======
  function init() {
    loadDict(function (data) {
      dict = data.terms || data;
      buildIndex();
      injectStyles();
      createPopover();
      scanAndAnnotate();
      bindEvents();
    });
  }

  // 加载词典
  function loadDict(cb) {
    // 优先级1：全局变量内联（最可靠，不受CORS限制）
    if (window.__AI_DICT) {
      cb(window.__AI_DICT);
      return;
    }

    var dictUrl = _dictUrl;
    if (!dictUrl) {
      console.warn('[glossary] 未找到词典数据，请设置 data-dict 或 window.__AI_DICT');
      return;
    }

    // 优先级2：script标签加载（绕过file://下的CORS限制）
    // 在file://协议下XMLHttpRequest会被CORS阻止，但<script>标签不受限制
    var protocol = window.location.protocol;
    if (protocol === 'file:') {
      loadDictViaScript(dictUrl, cb);
      return;
    }

    // 优先级3：XHR（http/https协议下正常使用）
    var xhr = new XMLHttpRequest();
    xhr.open('GET', dictUrl, true);
    xhr.onreadystatechange = function () {
      if (xhr.readyState === 4) {
        if (xhr.status === 200) {
          try { cb(JSON.parse(xhr.responseText)); }
          catch (e) { console.warn('[glossary] 词典解析失败', e); }
        } else {
          // XHR失败时降级到script标签
          console.warn('[glossary] XHR加载失败(status=' + xhr.status + ')，尝试script标签');
          loadDictViaScript(dictUrl, cb);
        }
      }
    };
    xhr.onerror = function () {
      // XHR被CORS阻止时降级到script标签
      console.warn('[glossary] XHR被阻止，尝试script标签');
      loadDictViaScript(dictUrl, cb);
    };
    xhr.send();
  }

  // 通过<script>标签加载JSON文件（绕过file://下的CORS限制）
  function loadDictViaScript(url, cb) {
    // 方案：创建一个临时script标签，把JSON文件内容作为JS执行
    // 但JSON不是合法JS表达式，所以需要一个小hack：
    // 用fetch的script import方式，或者用Object.assign包装
    var script = document.createElement('script');
    script.type = 'text/javascript';
    // 给URL加一个callback参数，让JSON文件可以自我包装成JS
    // 但我们的JSON是纯JSON没有callback，所以这里用另一种方式：
    // 先用<script>标签把JSON文件当作模块加载
    // 实际上最可靠的方式是直接内联——但JSON文件太大
    
    // 最终方案：使用<script src>加载一个自包装版本的JSON
    // 我们需要把JSON包装成 window.__AI_DICT = {...} 格式
    // 所以改用加载一个.js版本（而非.json）
    var jsUrl = url.replace('.json', '-inline.js');
    script.src = jsUrl;
    script.onload = function () {
      if (window.__AI_DICT) {
        cb(window.__AI_DICT);
      } else {
        console.warn('[glossary] script加载成功但window.__AI_DICT不存在');
      }
    };
    script.onerror = function () {
      console.warn('[glossary] script标签加载也失败了——词典数据不可用');
      // 最后的最后：尝试用内联数据
      if (window.__AI_DICT_INLINE) {
        cb(window.__AI_DICT_INLINE);
      }
    };
    document.head.appendChild(script);
  }

  // 建索引：term + aliases 都指向 entry
  function buildIndex() {
    for (var i = 0; i < dict.length; i++) {
      var entry = dict[i];
      if (entry.term) {
        dictByTerm[entry.term.toLowerCase()] = entry;
      }
      if (entry.aliases) {
        for (var j = 0; j < entry.aliases.length; j++) {
          var alias = entry.aliases[j];
          if (alias && alias.length >= MIN_TERM_LEN) {
            dictByAlias[alias.toLowerCase()] = entry;
          }
        }
      }
    }
  }

  // 注入 CSS（如果没手动引入）
  function injectStyles() {
    if (document.querySelector('link[href*="glossary.css"]')) return;
    if (document.getElementById('glossary-injected-style')) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'glossary.css';
    link.id = 'glossary-injected-style';
    document.head.appendChild(link);
  }

  // 创建浮层 DOM
  function createPopover() {
    popover = document.createElement('div');
    popover.className = 'glossary-popover';
    popover.innerHTML = '';
    document.body.appendChild(popover);
  }

  // ====== 扫描正文，标注术语 ======
  // 策略：先全局收集所有文本节点和匹配位置，再对每个术语只标注首次 + 末次（最多 2 次）
  function scanAndAnnotate() {
    var containers = document.querySelectorAll(SCAN_SELECTORS);

    // 1. 收集所有文本节点及其匹配
    var textNodes = []; // [{node, matches}]
    for (var i = 0; i < containers.length; i++) {
      collectTextNodes(containers[i], textNodes);
    }

    // 2. 统计每个术语的所有出现位置（跨文本节点）
    var termOccurrences = {}; // entryId -> [{nodeIdx, matchIdx}]
    for (var ni = 0; ni < textNodes.length; ni++) {
      var matches = textNodes[ni].matches;
      for (var mi = 0; mi < matches.length; mi++) {
        var id = matches[mi].entry.id;
        if (!termOccurrences[id]) termOccurrences[id] = [];
        termOccurrences[id].push({ nodeIdx: ni, matchIdx: mi });
      }
    }

    // 3. 对每个术语，只保留首次 + 末次（最多 2 次）
    var keepSet = new Set(); // "nodeIdx-matchIdx"
    for (var id in termOccurrences) {
      var occs = termOccurrences[id];
      if (occs.length === 0) continue;
      var first = occs[0];
      keepSet.add(first.nodeIdx + '-' + first.matchIdx);
      if (occs.length > 1) {
        var last = occs[occs.length - 1];
        keepSet.add(last.nodeIdx + '-' + last.matchIdx);
      }
    }

    // 4. 应用标注（只标注 keepSet 里的）
    var annotated = 0;
    for (var ni2 = 0; ni2 < textNodes.length && annotated < MAX_TERMS_PER_PAGE; ni2++) {
      var tn = textNodes[ni2];
      var node = tn.node;
      var text = node.nodeValue;
      var ms = tn.matches;
      if (ms.length === 0) continue;

      var frag = document.createDocumentFragment();
      var lastIdx = 0;
      for (var k = 0; k < ms.length; k++) {
        var m = ms[k];
        var key = ni2 + '-' + k;
        if (!keepSet.has(key)) continue; // 跳过不保留的

        if (m.start > lastIdx) {
          frag.appendChild(document.createTextNode(text.slice(lastIdx, m.start)));
        }
        var span = document.createElement('span');
        span.className = 'term-trigger';
        span.setAttribute('data-term-id', m.entry.id);
        span.setAttribute('data-term-name', m.entry.term);
        span.textContent = m.matched;
        frag.appendChild(span);
        lastIdx = m.end;
        annotated++;
        if (annotated >= MAX_TERMS_PER_PAGE) break;
      }
      if (lastIdx < text.length) {
        frag.appendChild(document.createTextNode(text.slice(lastIdx)));
      }
      if (frag.childNodes.length > 0) {
        node.parentNode.replaceChild(frag, node);
      }
    }
  }

  // 递归收集文本节点及其术语匹配
  function collectTextNodes(node, result) {
    if (node.nodeType === Node.TEXT_NODE) {
      var text = node.nodeValue;
      if (!text || text.trim().length < 2) return;
      if (shouldSkipParent(node.parentNode)) return;
      var matches = findTermsInText(text);
      if (matches.length > 0) {
        result.push({ node: node, matches: matches });
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      if (shouldSkipParent(node)) return;
      var children = node.childNodes;
      for (var i = 0; i < children.length; i++) {
        collectTextNodes(children[i], result);
      }
    }
  }

  function shouldSkipParent(el) {
    if (!el) return false;
    var tag = el.tagName;
    if (tag === 'SCRIPT' || tag === 'STYLE') return true;
    if (el.classList && el.classList.contains('term-trigger')) return true;
    return false;
  }

  // 在文本中查找所有术语匹配
  function findTermsInText(text) {
    var matches = [];
    var lower = text.toLowerCase();

    // 收集所有候选词
    var candidates = [];
    for (var term in dictByTerm) {
      if (dictByTerm.hasOwnProperty(term)) {
        candidates.push({ key: term, entry: dictByTerm[term] });
      }
    }
    for (var alias in dictByAlias) {
      if (dictByAlias.hasOwnProperty(alias)) {
        candidates.push({ key: alias, entry: dictByAlias[alias] });
      }
    }

    // 按长度降序（优先匹配长词，避免短词截断长词）
    candidates.sort(function (a, b) { return b.key.length - a.key.length; });

    var usedRanges = [];

    for (var i = 0; i < candidates.length; i++) {
      var c = candidates[i];
      var key = c.key;

      // 长度过滤
      var isChinese = /[\u4e00-\u9fa5]/.test(key);
      var minLen = isChinese ? MIN_TERM_LEN_ZH : MIN_TERM_LEN;
      if (key.length < minLen) continue;

      // 黑名单
      if (BLACKLIST.has(c.entry.term)) continue;
      if (BLACKLIST.has(key.toUpperCase())) continue;

      // 全局匹配所有出现位置
      var searchFrom = 0;
      while (true) {
        var idx = lower.indexOf(key, searchFrom);
        if (idx === -1) break;
        var end = idx + key.length;

        // 检查边界：前后不能是字母数字（避免匹配子串）
        if (!isWordBoundary(text, idx, end)) {
          searchFrom = idx + 1;
          continue;
        }

        // 检查是否与已匹配范围重叠
        if (!rangesOverlap(usedRanges, idx, end)) {
          matches.push({
            start: idx,
            end: end,
            matched: text.slice(idx, end),
            entry: c.entry
          });
          usedRanges.push({ start: idx, end: end });
        }
        searchFrom = end;
      }
    }

    // 按位置排序
    matches.sort(function (a, b) { return a.start - b.start; });
    return matches;
  }

  function isWordBoundary(text, start, end) {
    var before = start > 0 ? text[start - 1] : ' ';
    var after = end < text.length ? text[end] : ' ';
    // 前后是字母数字则不算边界（避免 GPT 匹配 GPTs 里的 GPT）
    var wordChar = /[a-zA-Z0-9]/;
    if (wordChar.test(before) && /[a-zA-Z]/.test(text[start])) return false;
    if (wordChar.test(after) && /[a-zA-Z]/.test(text[end - 1])) return false;
    return true;
  }

  function rangesOverlap(ranges, start, end) {
    for (var i = 0; i < ranges.length; i++) {
      var r = ranges[i];
      if (start < r.end && end > r.start) return true;
    }
    return false;
  }

  // ====== 浮层交互 ======
  function bindEvents() {
    document.addEventListener('click', function (e) {
      var trigger = e.target.closest('.term-trigger');
      if (trigger) {
        e.preventDefault();
        e.stopPropagation();
        showPopover(trigger);
        return;
      }
      // 点击外部关闭
      if (popover.classList.contains('show') && !popover.contains(e.target)) {
        hidePopover();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') hidePopover();
    });

    window.addEventListener('scroll', hidePopover, { passive: true });
    window.addEventListener('resize', hidePopover);
  }

  function showPopover(trigger) {
    var termId = trigger.getAttribute('data-term-id');
    var entry = findEntryById(termId);
    if (!entry) return;

    // 高亮当前触发词
    if (activeTrigger) activeTrigger.classList.remove('term-active');
    trigger.classList.add('term-active');
    activeTrigger = trigger;

    // 渲染内容
    popover.innerHTML = renderPopoverContent(entry);

    // 定位
    positionPopover(trigger);

    // 显示
    popover.classList.add('show');
  }

  function hidePopover() {
    popover.classList.remove('show');
    if (activeTrigger) {
      activeTrigger.classList.remove('term-active');
      activeTrigger = null;
    }
  }

  function positionPopover(trigger) {
    var rect = trigger.getBoundingClientRect();
    var popoverRect = popover.getBoundingClientRect();
    var top = rect.bottom + 8;
    var left = rect.left;

    // 防止溢出右侧
    if (left + popoverRect.width > window.innerWidth - 16) {
      left = window.innerWidth - popoverRect.width - 16;
    }
    // 防止溢出左侧
    if (left < 16) left = 16;

    // 如果下方空间不够，显示在上方
    if (top + popoverRect.height > window.innerHeight - 16) {
      top = rect.top - popoverRect.height - 8;
      if (top < 16) top = 16;
    }

    popover.style.top = top + 'px';
    popover.style.left = left + 'px';
  }

  function renderPopoverContent(entry) {
    var html = '';
    html += '<div class="gloss-popover-header">';
    html += '<div><span class="gloss-popover-term">' + escapeHtml(entry.term) + '</span>';
    if (entry.term_zh) {
      html += '<span class="gloss-popover-term-zh">' + escapeHtml(entry.term_zh) + '</span>';
    }
    html += '</div>';
    if (entry.category) {
      html += '<span class="gloss-popover-cat">' + escapeHtml(entry.category) + '</span>';
    }
    html += '</div>';

    if (entry.definition_short) {
      html += '<div class="gloss-popover-def">' + escapeHtml(entry.definition_short) + '</div>';
    }

    if (entry.why_it_matters) {
      html += '<div class="gloss-popover-why">';
      html += '<span class="gloss-popover-why-label">为什么重要</span>';
      html += escapeHtml(entry.why_it_matters);
      html += '</div>';
    }

    html += '<div class="gloss-popover-footer">';
    if (entry.related_terms && entry.related_terms.length > 0) {
      var related = entry.related_terms.slice(0, 3).join(' · ');
      html += '<span class="gloss-popover-related"><strong>相关：</strong>' + escapeHtml(related) + '</span>';
    } else {
      html += '<span class="gloss-popover-related"></span>';
    }
    html += '<button class="gloss-popover-close" type="button">关闭</button>';
    html += '</div>';

    return html;
  }

  function findEntryById(id) {
    for (var i = 0; i < dict.length; i++) {
      if (dict[i].id === id) return dict[i];
    }
    return null;
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ====== 启动 ======
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // 暴露 API（供新词反哺机制调用）
  window.AINewsGlossary = {
    getDict: function () { return dict; },
    getAnnotatedTerms: function () {
      var triggers = document.querySelectorAll('.term-trigger');
      var seen = {};
      var result = [];
      for (var i = 0; i < triggers.length; i++) {
        var id = triggers[i].getAttribute('data-term-id');
        if (!seen[id]) {
          seen[id] = true;
          result.push(triggers[i].getAttribute('data-term-name'));
        }
      }
      return result;
    },
    rescan: function () {
      // 移除旧标注，重新扫描
      var old = document.querySelectorAll('.term-trigger');
      for (var i = 0; i < old.length; i++) {
        var parent = old[i].parentNode;
        parent.replaceChild(document.createTextNode(old[i].textContent), old[i]);
        parent.normalize();
      }
      scanAndAnnotate();
    }
  };
})();
