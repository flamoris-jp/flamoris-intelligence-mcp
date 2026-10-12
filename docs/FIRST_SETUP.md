# Intelligence MCP：Updaterの入力値と導入後の設定

対象は公開済み1.0.2のインストール定義です。別の版では選定Releaseのカタログと[インストール定義](../release/install-recipe.json)を照合します。
Updaterの画面には短い項目名が表示されます。本書で用途・取得元・空欄時の動作を確認してください。
既定値は入力欄の初期値で、generate=true以外の欄を空にしても自動生成されません。
共通のDB・秘密値の扱い、配置の調べ方、作業の順番は[共通設定ガイド](https://github.com/flamoris-jp/flamoris-updater/blob/main/docs/APPLICATION_SETUP.md)にあります。

## 導入前に用意するもの

動作するllama.cppと提供モデルを用意します。これは外部クライアント用MCP facadeです。
Studio／Agentの内部推論は共有adapterからproviderへ接続し、このMCP listenerの導入を必須にしません。

## Updaterに入力する値

| 項目（キー） | 用途・値の用意 | 初期表示／空欄の動作 |
| --- | --- | --- |
| 待受ポート（PORT） | 外部Intelligence MCPサービスの入口。未使用のポートを選ぶ | 8767 |
| llama.cppのURL（PROVIDER_URL） | 既存モデルserviceのbase URLをservice設定から取得。Hub／MCPのURLではない | http://127.0.0.1:8081 |
| モデル対応JSON（MODELS_JSON） | 公開するidは運用者が選び、provider_modelは実際のproviderのモデル一覧から取得。両者を対応付ける | gpt-oss-20bの例が入る。実機のserved IDと一致するか確認 |

入力例の構造は次です。provider_modelは実際のGET /v1/modelsのdata[].idに置き換えます。

```json
[{"id":"local-model","provider_model":"actual-served-model-id"}]
```

公開id、実際に提供されるmodel ID、モデルファイルpathは同じ意味ではありません。
この初回recipeにはAPI key／service token入力欄はありません。外部公開の接続境界は導入環境で設定します。

## 導入後にユーザー／AIが行うこと

1. Updaterで起動し、providerの到達性とモデルID対応を確認する。
2. [契約](CONTRACT.md)に沿ってhealth・capability・modelのmetadataを確認する。モデルserviceは必要なら正規Managerで起動する。
3. 外部クライアント／Hubを使う場合だけ、接続URL・Host・外部認証境界とmatched catalogを設定する。[Docker／HTTP](DOCKER.md)を参照する。
4. 選定したlocalモデルの小さな推論で結果を確認する。起動healthだけで推論成功にしない。
5. OpenAIを選ぶ場合だけ、providerが発行するAPI key、モデル・利用上限を[OpenAI adapter](OPENAI_RESPONSES.md)へ設定する。初回recipeの3入力から自動生成される値ではない。

## AIに渡すとき

選定版、provider URL、公開idとserved IDの対応、外部MCPを誰から利用するかを伝えます。
API key等の値は会話へ貼らず、provider側の既存設定をローカルで扱います。
