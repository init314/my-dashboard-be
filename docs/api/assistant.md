# SENTIS AI 비서 API

모든 경로는 OWNER 세션 인증을 요구하고 POST/DELETE는 기존 CSRF 헤더가 필요하다. 다른 로그인 세션의 job ID는 404다. request 값으로 실행 장비·작업 폴더·권한을 선택할 수 없다.

| Method | Path | Query / body | 성공 |
| --- | --- | --- | --- |
| GET | /api/v1/assistant | 없음 | 200 AssistantProject |
| POST | /api/v1/assistant/jobs | AssistantRequest | 202 Studio JobView |
| GET | /api/v1/assistant/jobs/{id} | 필수 non-null String id | 200 Studio JobView |
| DELETE | /api/v1/assistant/jobs/{id} | 필수 non-null String id | 204, 취소 |
| POST | /api/v1/assistant/jobs/{id}/inputs | 필수 non-null String id, Assistant Control | 204 |

AssistantProject: deviceId와 root는 필수 non-null String이다. deviceId는 항상 local, root는 서버 파일 루트 하위 실제 `.assistant` 절대 경로다. GET에서 해당 폴더를 준비한다. 기존 파일 또는 심볼릭 링크로 대체되어 있으면 403, 경로/권한 등 준비 실패는 409다.

AssistantRequest: action은 필수 non-null String, 최대 40자다. args는 선택/null 허용이며 생략하면 빈 입력으로 처리한다. action 허용값은 setup, codex-run, codex-login, codex-status, codex-models, codex-account, codex-connections, codex-threads, codex-thread-new, codex-thread-read, codex-thread-rename, codex-thread-archive, codex-thread-unarchive, codex-thread-fork, codex-thread-compact, codex-thread-rollback이다. setup은 기존 Codex 설치·해시 검사만 실행하고 GitHub CLI는 설치하지 않는다. codex-login은 유효한 저장 인증이 있으면 재사용하고 authenticated=true로 완료하며, 인증이 없을 때만 기기 코드 인증을 실행한다.

args의 필드·타입·길이·null 규칙은 [Studio Args 및 action 계약](studio.md)을 재사용한다. 비서에서 사용되는 필드는 prompt, threadId, model, effort, mode, context, name, query, cursor, archived다. mode는 요청 값과 무관하게 서버가 danger-full-access로 덮어쓰며 새 대화와 재개에 approvalPolicy=never를 지정한다. context는 선택/null 허용 List, 최대 16개이며 image 종류만 허용한다. 이미지의 name/dataUrl 형식·크기는 기존 Studio context 계약과 같다. 직접 파일·selection·skill 첨부는 400이다. 그 외 Studio Args 필드는 해당 action에서 사용하지 않는다.

JobView, Result, Assistant Result/Thread/Item/Event/Usage, Control의 전체 필드와 optional/null·enum 규칙은 [Studio 계약](studio.md)과 동일하다. Control.type은 approval/answer/steer/interrupt, decision은 accept/acceptForSession/decline/cancel을 재사용하며 실행 중 codex-run 또는 codex-thread-compact만 제어할 수 있다. MCP item은 기존 Item의 type=mcpToolCall로 도구 이름·결과 텍스트를 투영한다. 응답에 연결 쿠키·원본 MCP 설정은 없다.

동일 OWNER 로그인 세션의 Studio job 저장소·최대 4개 실행·32개 보유·최근 150개/200,000자 이벤트·15분 실행/30분 보유·로그아웃 정리를 재사용한다. 동일 세션에서는 양쪽 job URL로 같은 소유 작업에 접근할 수 있다. 비서의 대화 조회는 `.assistant` cwd에 한정하고 다른 프로젝트 thread는 403으로 거절한다. 자동 실행 재시도는 없다.

오류: 공통 401(세션 없음), 403(OWNER/CSRF 없음), 400(미지원 action/입력/context), 413(전체 첨부 크기), 429(동시 실행 한도), job 조회·제어·취소 404(미존재/다른 세션), inputs 409(실행 종료/연결 미준비). 접수 이후 helper·MCP 실패는 HTTP 200 JobView의 FAILED/error/errorStatus로 전달한다. missing CLI/파일 404, 잘못된 대상 thread 403, folder 충돌 409, 응답 한도 413, 서버 연결/CLI 실패 502, App Server 응답 제한 504, Linux 아닌 local 환경 400이다. message는 사용자 설명이며 코드로 파싱하지 않는다.

## 내부 MCP 제어 계약

`dashboard_assistant` stdio MCP 1.1.0의 도구이며 별도 공개 HTTP 엔드포인트를 추가하지 않는다. 기존 조회 도구 9개는 [비서 기능](../assistant.md)을 따른다. 아래 입력은 알 수 없는 필드와 최상위 null을 거부한다. 문자열에는 제어 문자를 허용하지 않는다. 모든 결과는 MCP `content[{type:"text",text:JSON문자열}]`로 반환한다.

| 도구 | 입력 | 성공 결과 |
| --- | --- | --- |
| dashboard_context | 빈 object | sourceRoot:String, sourceAvailable:Boolean, sourceWritable:Boolean, apiPrefix:String, endpoints:String, truncated:Boolean, instructionsFile:String, contracts:String[], guidance:String[] (모두 필수/non-null) |
| dashboard_request | method:필수 String GET/POST/PUT/PATCH/DELETE, path:필수 String 최대 4096자, query:선택 Object, body:선택 Object 또는 Array | status:필수 Integer HTTP 상태, data:필수 JSON 값 또는 본문 없는 응답의 null |
| dashboard_upload | path:필수 String 최대 4096자, filePath:필수 String 최대 4096자, query:선택 Object | status:필수 Integer HTTP 상태, data:필수 JSON 값 또는 null |

path는 `/api/v1` 뒤의 `/`로 시작하는 상대 경로다. 호스트 URL, 쿼리·fragment, 역슬래시, 중복 슬래시, `.`/`..` 경로 및 이를 중첩 percent-encoding한 입력을 거부한다. 인증은 서버가 지정한 127.0.0.1과 실제 포트에만 전송하며 리디렉션은 따르지 않는다. query는 임의 필드 이름과 문자열·유한한 숫자·boolean 또는 그 배열을 허용하며 URL 인코딩한다. 중첩 object와 null은 허용하지 않는다. body의 내부 필드·null·enum·revision은 호출하는 기존 API 계약을 따른다. GET body는 거부한다. DELETE body는 해당 API가 요구할 때만 사용한다.

JSON 요청·응답은 1 MiB 이내이며 stdio 한 메시지 입력은 128 KiB 이내다. 연결·각 socket 읽기/쓰기는 15초 제한이고 자동 재시도하지 않는다. 파일은 컨테이너에서 읽을 수 있는 절대 경로의 일반 파일이며 multipart `file` 필드로 최대 1 GiB를 64 KiB씩 스트리밍한다. 서버 업로드 설정·기능별 제한(예: 메모 이미지 10 MiB)도 적용된다. 전체 파일 내용을 도구 JSON에 넣지 않는다. 업로드 응답은 기존 API DTO다. 바이너리 다운로드는 `download_file` 링크를 사용한다.

상태 변경은 같은 세션의 홈 meta에서 CSRF 값을 한 번 읽어 전송하며 쿠키·CSRF 값은 도구 결과에 포함하지 않는다. MCP 요청은 기존 API/service OWNER·CSRF·revision 검사 및 기존 감사/검증 흐름을 그대로 거친다. 2xx는 성공이고 204 등 빈 본문은 data=null이다. 세션 만료 401, 나머지 HTTP 실패(400/403/404/409/413 등), 잘못된 입력·CSRF 누락·소스 파일 없음·응답 한도·전송 실패는 `isError=true`와 자격증명을 포함하지 않는 메시지로 반환한다. 변경 후 응답이 유실되면 도구 실패여도 변경이 적용됐을 수 있으므로 현재 상태를 조회한다. 두 변경 도구는 readOnlyHint=false/destructiveHint=true이며 context와 기존 조회 도구는 readOnlyHint=true다.
