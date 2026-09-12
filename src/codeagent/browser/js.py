"""JS snippets injected into the software's own browser window."""

from __future__ import annotations

import json

SNAPSHOT_JS = """
(function(){
  var nodes=[];
  var sel='a[href], button, input, textarea, select, [role=button]';
  var els=document.querySelectorAll(sel);
  for(var i=0;i<els.length && i<80;i++){
    var el=els[i];
    var ref='@e'+(i+1);
    el.setAttribute('data-cca-ref', ref);
    var text=(el.innerText||el.value||el.getAttribute('aria-label')||
              el.getAttribute('placeholder')||'').replace(/\\s+/g,' ').trim().slice(0,80);
    nodes.push({
      ref:ref,
      tag:(el.tagName||'').toLowerCase(),
      type:el.type||'',
      text:text,
      href:el.href||'',
      name:el.name||''
    });
  }
  var body=(document.body && document.body.innerText || '').replace(/\\s+/g,' ').trim().slice(0,6000);
  return JSON.stringify({
    url: location.href,
    title: document.title||'',
    text: body,
    nodes: nodes
  });
})()
""".strip()


def click_js(ref: str) -> str:
    sel = json.dumps(f'[data-cca-ref="{ref}"]')
    return (
        "(function(){var el=document.querySelector(" + sel + ");"
        "if(!el)return 'missing';el.click();return 'ok';})()"
    )


def fill_js(ref: str, value: str) -> str:
    sel = json.dumps(f'[data-cca-ref="{ref}"]')
    val = json.dumps(value)
    return (
        "(function(){var el=document.querySelector(" + sel + ");"
        "if(!el)return 'missing';el.focus();"
        "if(el.isContentEditable){el.innerText=" + val + ";}"
        "else{el.value=" + val + ";}"
        "el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));"
        "return 'ok';})()"
    )


def press_js(key: str) -> str:
    val = json.dumps(key)
    return (
        "(function(){var el=document.activeElement||document.body;"
        "var k=" + val + ";"
        "el.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true}));"
        "if(k==='Enter'&&el.form){el.form.requestSubmit?el.form.requestSubmit():el.form.submit();}"
        "return 'ok';})()"
    )


def select_js(ref: str, value: str) -> str:
    sel = json.dumps(f'[data-cca-ref="{ref}"]')
    val = json.dumps(value)
    return (
        "(function(){var el=document.querySelector(" + sel + ");"
        "if(!el)return 'missing';el.value=" + val + ";"
        "el.dispatchEvent(new Event('change',{bubbles:true}));return 'ok';})()"
    )
