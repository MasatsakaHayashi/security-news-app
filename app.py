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

# タイトルの縮小（スマホのファーストビュー改善）
st.markdown("<h2 style='text-align: center; font-size: 1.6rem; margin-top: -30px; margin-bottom: 20px;'>📰 ニュース収集ダッシュボード</h2>", unsafe_allow_html=True)

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

st.sidebar.markdown("---")
st.sidebar.subheader("📱 動作軽量化・表示設定")
display_limit = st.sidebar.slider("最大表示件数", min_value=10, max_value=300, value=50, step=10, help="動作が重い（カクつく）場合は、表示件数を減らしてください。")
show_summary = st.sidebar.checkbox("記事の要約テキストを表示する", value=False, help="チェックを外すとDOM描画量が激減し、スマホでのスクロールが非常に軽くなります。")

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

# ユーザーUXの向上：画面全体をグレーアウトして操作をブロックするオーバーレイを表示
loading_overlay = st.empty()
loading_overlay.markdown("""
    <style>
    .loading-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(5px);
        z-index: 999999;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-direction: column;
        color: white;
        text-align: center;
    }
    .spinner-custom {
        border: 5px solid rgba(255, 255, 255, 0.2);
        border-radius: 50%;
        border-top: 5px solid #ffffff;
        width: 60px;
        height: 60px;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    <div class="loading-overlay">
        <div class="spinner-custom"></div>
        <h2>📡 最新のニュース情報を収集しています...</h2>
        <p style="font-size: 1.1em;">新規取得には数秒〜数十秒かかる場合があります。<br>画面はこのまま触らずにお待ちください。</p>
    </div>
""", unsafe_allow_html=True)

entries = fetch_all_news(target_keywords)

# 取得が終わったらオーバーレイごと消去する
loading_overlay.empty()

if entries:
    display_entries = entries[:display_limit]
    
    if search_query == "すべて（ホーム画面）":
        st.success(f"検索結果: {len(entries)} 件（うち最新の {len(display_entries)} 件を表示中）")
    else:
        st.success(f"「{search_query}」の検索結果: {len(entries)} 件（うち最新の {len(display_entries)} 件を表示中）")
        
    # スマホ向けに視認性を高めた「SmartNews風」カードブロックレイアウト
    # CSS定義（グリッドレイアウトとカードデザイン）
    st.markdown("""
<style>
.smart-grid {
    display: grid;
    /* PCではカード幅を広く取り、見出しが1-2行に収まるようにする（スマホ画面は下の@mediaで上書きされます） */
    grid-template-columns: repeat(auto-fill, minmax(700px, 1fr));
    gap: 20px;
    padding: 15px 0;
}
.smart-card {
    background-color: var(--background-color);
    border: 1px solid var(--secondary-background-color);
    border-top: 5px solid var(--primary-color);
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0px 4px 15px rgba(0,0,0,0.1);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.2s, box-shadow 0.2s;
    height: 100%;
}
.smart-card:hover {
    transform: translateY(-4px);
    box-shadow: 0px 10px 20px rgba(0,0,0,0.15);
}
.smart-card-title {
    font-size: 1.1rem;
    font-weight: bold;
    line-height: 1.4;
    margin-bottom: 12px;
}
.smart-card-title a {
    text-decoration: none;
    color: var(--text-color);
}
.smart-card-title a:hover {
    color: var(--primary-color);
    text-decoration: underline;
}
.smart-card-meta {
    font-size: 0.85em;
    color: var(--text-color);
    opacity: 0.6;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.smart-meta-tag {
    background-color: var(--secondary-background-color);
    padding: 4px 8px;
    border-radius: 12px;
}
.smart-card-summary {
    font-size: 0.85em;
    margin-top: 12px;
    padding: 10px;
    background-color: var(--secondary-background-color);
    border-radius: 8px;
    color: var(--text-color);
    opacity: 0.8;
}

/* スマホ表示専用（PC側のデザインを崩さず、文字・余白を極限まで縮小して1画面の表示数を最大化する） */
@media screen and (max-width: 768px) {
    .smart-grid {
        grid-template-columns: 1fr;
        gap: 8px; /* カード間のすきまを極小化 */
        padding: 4px 0;
    }
    .smart-card {
        padding: 10px 12px; /* スマホではカード内余白を極小化 */
        border-top: 3px solid var(--primary-color);
        border-radius: 6px; /* 角枠を少しシャープにしてスペース削減 */
        box-shadow: 0px 1px 4px rgba(0,0,0,0.1);
    }
    .smart-card-title {
        font-size: 0.95rem; /* タイトル文字を読みやすさを維持した限界まで縮小 */
        margin-bottom: 6px;
        line-height: 1.3;
    }
    .smart-card-meta {
        font-size: 0.75em;
    }
    .smart-meta-tag {
        padding: 2px 6px; /* タグの余白も極限まで削る */
        border-radius: 4px;
    }
    .smart-card-summary {
        font-size: 0.75em;
        margin-top: 6px;
        padding: 8px;
    }
}
</style>
""", unsafe_allow_html=True)

    news_html_blocks = []
    
    for entry in display_entries:
        kw_tags = ", ".join(entry["source_keywords"])
        title = entry.get("title", "無題")
        date = entry.get("published", "日付不明")
        link = entry.get("link", "#")
        
        summary_block = ""
        if show_summary:
            summary = entry.get("summary", "")
            summary_block = f'<div class="smart-card-summary">{summary}</div>'

        # カード1枚分のHTML（改行を完全に取り除き、Markdownによるコードブロック化・レイアウト破壊のバグを防ぐ）
        card_html = f"""
        <div class="smart-card">
            <div class="smart-card-title">
                <a href="{link}" target="_blank">{title}</a>
            </div>
            <div style="margin-top: auto; padding-top: 8px;">
                <div class="smart-card-meta">
                    <span>📅 {date}</span>
                    <span class="smart-meta-tag">🏷️ {kw_tags}</span>
                </div>
                {summary_block}
            </div>
        </div>
        """.replace('\n', '')
        news_html_blocks.append(card_html)
        
    # 全てのカードをグリッドコンテナで囲んで一気に描画
    st.markdown('<div class="smart-grid">' + "".join(news_html_blocks) + '</div>', unsafe_allow_html=True)
else:
    st.warning("ニュースが見つかりませんでした。別のキーワードをお試しください。")
