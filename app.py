import streamlit as st
import feedparser
from urllib.parse import quote
import os
import json

# カスタマイズの保存先ファイル
KEYWORDS_FILE = "custom_keywords.json"
DEFAULT_HOME_KEYWORDS = "セキュリティ, AI"
DEFAULT_SEARCH_KEYWORDS = "セキュリティ, AI, クラウド, Python, テクノロジー"

def load_keywords():
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                home = data.get("home_keywords", data.get("keywords", DEFAULT_HOME_KEYWORDS))
                search = data.get("search_keywords", data.get("keywords", DEFAULT_SEARCH_KEYWORDS))
                return home, search
        except Exception:
            pass
    return DEFAULT_HOME_KEYWORDS, DEFAULT_SEARCH_KEYWORDS

def save_keywords(home_str, search_str):
    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "home_keywords": home_str,
            "search_keywords": search_str
        }, f, ensure_ascii=False)

# ページ設定
st.set_page_config(page_title="ニュース収集ダッシュボード", page_icon="📰", layout="wide")

st.title("📰 ニュース収集ダッシュボード")

# サイドバー: 検索機能
st.sidebar.header("検索設定")

# キーワードのリストを自由に設定できるようにする
with st.sidebar.expander("📝 選択項目のカスタマイズ", expanded=False):
    loaded_home, loaded_search = load_keywords()
    
    # 既存のカンマ区切り文字列をリストに変換
    current_home_list = [k.strip() for k in loaded_home.split(",") if k.strip()]
    current_search_list = [k.strip() for k in loaded_search.split(",") if k.strip()]
    
    st.markdown("**🏠 ホーム画面の一括検索用**")
    st.caption("※下の表の最後の行をクリックして新しく追加できます。行を選択してDelete（Backspace）キーで削除できます。")
    home_data = [{"キーワード": k} for k in current_home_list]
    # data_editorで視覚的に編集できるようにする
    edited_home = st.data_editor(home_data, num_rows="dynamic", key="home_editor", use_container_width=True)
    
    st.markdown("**🔍 個別検索のプルダウン用**")
    st.caption("※同様に追加・削除が可能です。")
    search_data = [{"キーワード": k} for k in current_search_list]
    edited_search = st.data_editor(search_data, num_rows="dynamic", key="search_editor", use_container_width=True)
    
    # 編集結果のリストを再構築（空文字は除外）
    new_home_list = [d["キーワード"].strip() for d in edited_home if d.get("キーワード", "").strip()]
    new_search_list = [d["キーワード"].strip() for d in edited_search if d.get("キーワード", "").strip()]
    
    # エラー回避のため空の場合はデフォルトを設定
    if not new_home_list:
        new_home_list = ["セキュリティ"]
    if not new_search_list:
        new_search_list = ["セキュリティ"]
        
    new_home_str = ",".join(new_home_list)
    new_search_str = ",".join(new_search_list)
    
    # 変更があった場合のみ保存
    if new_home_str != loaded_home or new_search_str != loaded_search:
        save_keywords(new_home_str, new_search_str)

# 以下の検索処理にはエディタ経由で取得した新しいリストを渡す
home_keyword_list = new_home_list
search_keyword_list = new_search_list

# 表示するキーワードの絞り込み UI
search_query = st.sidebar.selectbox("キーワードを選択", options=["すべて（ホーム画面）"] + search_keyword_list, index=0)

# ニュースを取得する機能 (Streamlitのキャッシュを利用して高速化)
@st.cache_data(ttl=900)  # 15分キャッシュ
def fetch_all_news(keywords):
    import time
    all_entries = {}
    
    for kw in keywords:
        encoded_query = quote(kw)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(rss_url)
        
        for entry in feed.entries:
            link = getattr(entry, 'link', None)
            if not link:
                continue
                
            if link not in all_entries:
                entry_dict = {
                    "title": getattr(entry, 'title', '無題'),
                    "link": link,
                    "published": getattr(entry, 'published', '発行日不明'),
                    "summary": getattr(entry, 'summary', '要約はありません。'),
                    "source_keywords": [kw],
                    "sort_key": 0
                }
                
                parsed = getattr(entry, 'published_parsed', None)
                if parsed:
                    try:
                        entry_dict["sort_key"] = time.mktime(parsed)
                    except Exception:
                        pass
                
                all_entries[link] = entry_dict
            else:
                if kw not in all_entries[link]["source_keywords"]:
                    all_entries[link]["source_keywords"].append(kw)
                    
    # 日付の降順でソート
    sorted_entries = sorted(all_entries.values(), key=lambda x: x["sort_key"], reverse=True)
    return sorted_entries

# 検索対象の確定
if search_query == "すべて（ホーム画面）":
    target_keywords = home_keyword_list
else:
    target_keywords = [search_query]

with st.spinner("ニュースを取得中..."):
    entries = fetch_all_news(target_keywords)

if entries:
    if search_query == "すべて（ホーム画面）":
        st.success(f"ホーム画面用キーワード（{len(target_keywords)}個）から {len(entries)} 件のニュースを取得しました。")
    else:
        st.success(f"「{search_query}」の関連ニュースを {len(entries)} 件取得しました。")
        
    # ニュースをカード型デザインで並べて表示
    for entry in entries:
        with st.container(border=True):
            # 関連キーワードのタグ表示
            kw_tags = ", ".join(entry["source_keywords"])
            st.caption(f"🏷️ 関連キーワード: {kw_tags}")
            
            # 記事タイトル
            st.subheader(entry["title"])
            
            # 発行日
            st.caption(f"📅 発行日: {entry['published']}")
            
            # 要約 (Google Newsの場合、HTMLが含まれることがあるため表示を工夫)
            st.markdown(entry["summary"], unsafe_allow_html=True)
            
            # 元記事へのリンクボタン
            if entry.get("link"):
                st.link_button("🔗 元記事を読む", entry["link"])
else:
    st.warning("ニュースが見つかりませんでした。別のキーワードをお試しください。")
