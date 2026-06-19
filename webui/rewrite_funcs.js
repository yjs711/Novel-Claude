// ── doRewrite (toolbar) → 聚焦AI改写模块 ──
function doRewrite() {
  var out = el('rewriteOutput');
  if (out) { var body = out.parentElement; if (body.classList.contains('collapsed')) body.classList.remove('collapsed'); }
  var inp = el('rewritePrompt'); if (inp) { inp.focus(); inp.select(); }
  var ta = el('editorTextarea');
  if (ta) {
    var sel = ta.value.substring(ta.selectionStart, ta.selectionEnd);
    var st = el('rewriteStatus');
    if (sel) { if (st) { st.textContent = '已选中 ' + sel.length + ' 字'; st.style.color = 'var(--accent)'; } }
    else { if (st) { st.textContent = '请先选中要改写的文本'; st.style.color = 'var(--danger)'; } }
  }
}

// ── doRewriteExec (AI改写模块执行) ──
var _rewriteAbort = null;
function doRewriteExec() {
  var ta = el('editorTextarea'); if (!ta) return;
  var selText = ta.value.substring(ta.selectionStart, ta.selectionEnd);
  if (!selText) { showToast('请先选中要改写的文本', true); return; }
  var rp = el('rewritePrompt'); var promptText = rp ? rp.value.trim() : '';
  if (!promptText) { showToast('请输入改写要求', true); if (rp) rp.focus(); return; }

  var out = el('rewriteOutput'); var st = el('rewriteStatus');
  if (out) { out.style.display = ''; out.textContent = ''; }
  if (st) { st.textContent = '改写中...'; st.style.color = 'var(--text2)'; }
  el('btnRewriteCancel').style.display = '';

  var ac = new AbortController(); _rewriteAbort = ac;
  var rewritten = ''; var ch = parseInt(el('selChapter').value) || 1;

  fetch('/api/deai-rewrite', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content: selText, full_text: ta.value, chapter: ch, prompt: promptText}),
    signal: ac.signal
  }).then(function(resp) {
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    var reader = resp.body.getReader(); var decoder = new TextDecoder(); var buffer = '';
    (function readChunk() {
      reader.read().then(function(result) {
        if (result.done) {
          ta.value = ta.value.substring(0, ta.selectionStart) + rewritten + ta.value.substring(ta.selectionEnd);
          updateWordCount(); _rewriteAbort = null; el('btnRewriteCancel').style.display = 'none';
          if (st) { st.textContent = '完成 - ' + rewritten.length + ' 字已替换'; st.style.color = 'var(--success)'; }
          return;
        }
        buffer += decoder.decode(result.value, {stream: true});
        var lines = buffer.split('\n'); buffer = lines.pop() || '';
        for (var i = 0; i < lines.length; i++) {
          var line = lines[i]; if (line.startsWith(': ')) continue;
          if (!line.startsWith('data: ')) continue;
          try { var d = JSON.parse(line.slice(6));
            if (d.text) { rewritten += d.text; if (out) out.textContent = rewritten; }
            if (d.error && st) { st.textContent = '错误: ' + d.error; st.style.color = 'var(--danger)'; }
          } catch(e) {}
        }
        if (out) out.scrollTop = out.scrollHeight; readChunk();
      }).catch(function(e) {
        if (e.name === 'AbortError') return;
        if (st) { st.textContent = '流中断: ' + e.message; st.style.color = 'var(--danger)'; }
        _rewriteAbort = null; el('btnRewriteCancel').style.display = 'none';
      });
    })();
  }).catch(function(e) {
    if (e.name === 'AbortError') return;
    if (st) { st.textContent = '请求失败: ' + e.message; st.style.color = 'var(--danger)'; }
    _rewriteAbort = null; el('btnRewriteCancel').style.display = 'none';
  });
}

function cancelRewrite() {
  if (_rewriteAbort) { _rewriteAbort.abort(); _rewriteAbort = null; }
  el('btnRewriteCancel').style.display = 'none';
  var st = el('rewriteStatus'); if (st) { st.textContent = '已取消'; st.style.color = 'var(--text3)'; }
}
