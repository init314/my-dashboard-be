# SENTIS 개인 AI 비서

홈 상단의 **SENTIS**에 명령을 입력한다. 앱 목록에서 SENTIS를 열거나 카드의 확대 버튼으로 전체 화면 대화를 연다. 홈과 전체 화면은 같은 DOM·대화·실행 상태를 공유한다. 기존 홈 격자 배치와 IDE 프로젝트 대화는 별도로 유지한다.

## 시작과 사용

1. **도구 준비**로 공식 Codex CLI 0.157.1 전체 패키지를 SHA256 검증 후 설치한다. 본체·codex-code-mode-host·검색 및 sandbox 보조 파일을 함께 설치한다. 설치 버전이 다르거나 필수 보조 파일이 없으면 복구하고, 완전한 같은 버전이면 재사용한다. 비서 준비는 GitHub CLI를 설치하지 않는다. 인증 캐시와 대화 기록은 유지한다.
2. 홈을 열면 기존 서버 CLI 인증으로 모델·계정·저장된 대화를 자동으로 불러온다. 인증되면 로그인 버튼을 숨긴다. 최초 사용 또는 인증 만료 때만 **Codex 로그인**을 눌러 공식 기기 코드 인증 페이지에서 로그인한다. 유효한 인증이 있으면 로그인 요청도 이를 재사용한다. **연결 확인**으로 상태를 다시 조회할 수 있다.
3. “오늘 일정과 수업 알려줘”, “내일 오후 3시에 회의 추가해줘”, “메모장에 업무 기록 만들어줘”, “이 앱 이름 바꿔줘”, “등록 서버에서 이 파일 찾아서 다운로드 링크 줘”, “대시보드 홈 UI 코드를 수정하고 반영해줘”처럼 요청한다. Enter로 전송, Shift+Enter로 줄바꿈한다. **대시보드 제어** 빠른 요청은 기능과 소스 연결 상태를 확인할 명령을 입력한다.

홈 조회는 오늘 일정과 전용 작업 폴더를 준비하고 Codex의 모델·계정 상태 및 이전 대화를 조회하며 CLI 설치·기기 코드 로그인·유료 모델 실행을 시작하지 않는다. 인증은 영구 dashboard-data 볼륨 아래 서버 HOME의 `.codex` 캐시를 재사용한다. 브라우저에는 인증 토큰을 저장하거나 반환하지 않는다. Codex가 사용 중 인증을 자동 갱신한다. 인증이 취소되거나 만료되어 갱신할 수 없으면 재인증이 필요하다. 날짜 기준은 Asia/Seoul이다. 사이드 카드에는 저장된 오늘 일정 최대 4개를 표시한다. 수업은 비서 요청으로 조회한다. 모바일은 대화에 집중하며 사이드 카드를 감춘다.

모델·추론 강도, 새 세션·검색·복원·이름 변경·분기·보관·압축을 제공한다. 실행 중 입력은 현재 turn에 추가 지시를 보내며 중지 버튼은 turn/interrupt다. 실행 취소와 계정 인증은 별도 동작이다. 이미지 첨부는 기존 2 MB PNG/JPEG/WebP 계약을 사용한다. 파일은 MCP 도구로 조회한다.

## 연결과 범위

홈에서 모델·인증 확인 후 MCP 도구도 조회한다. 헤더의 “MCP 도구 12개 사용 가능”은 dashboard_assistant가 실제로 노출한 도구 수다. 세션 메뉴의 MCP 연결 상태는 서버별 도구 수를 표시한다. OAuth를 사용하지 않는 stdio MCP의 authStatus=unsupported는 오류가 아니다. 도구가 보이는데 실행에 실패하면 Codex 전체 패키지의 codex-code-mode-host 누락 여부를 먼저 확인하고 **도구 준비**로 복구한다. 0.157.1 본체만 설치했을 때 발생한 code-mode host 누락을 재현했으며, 패키지 복구 후 운영 AI 비서의 current_time·timetables 실제 호출을 검증했다.

추가 HTTP MCP는 서버 `~/.codex/config.toml`에 등록한다. 호스트 프록시가 `403 Invalid Host`를 반환하면 프록시가 허용하는 실제 주소를 사용한다. 현재 운영 프록시의 허용 주소는 `http://mcp-gateway.example:8765/mcp/...`이며, 거부되던 `host.docker.internal` 주소 9개를 이 주소로 수정했다. 인증 헤더를 유지하고 기존 설정은 동일한 비공개 Codex 디렉토리에 백업한다. PC별 MCP는 해당 PC와 Tailscale·SSH 연결이 온라인이어야 한다. `noTools`는 도구를 발견하지 못한 상태이며 다른 서버의 MCP 사용을 차단하지 않는다.

AssistantController → AssistantService → StudioService → StudioAdapter → 고정 Python helper → Codex App Server stdio를 사용한다. 실행 대상은 서버의 local 장비, 시작 작업 폴더는 파일 루트의 `.assistant`로 고정한다. 실제 디렉토리만 허용하고 심볼릭 링크를 거부한다. 새 대화와 기존 대화 재개 모두 sandbox=danger-full-access, approvalPolicy=never로 실행한다. 사용자 요청에 따른 파일·일정·코드·서버 설정 변경과 명령 실행을 허용한다. 접근 범위는 dashboard 컨테이너의 OS 계정, 마운트, 네트워크 및 사용 가능한 인증 권한에 따른다. 이 설정 자체가 호스트 관리자 권한이나 외부 계정 권한을 부여하지 않는다. dashboard_assistant는 기존 조회 도구 9개와 전체 제어용 도구 3개를 제공한다. 요청에서 다른 실행 장비·시작 폴더를 선택할 수 없다.

서버가 현재 HTTP 로그인 세션과 실제 loopback 포트로 dashboard_assistant MCP 연결을 구성한다. 고정 MCP 스크립트는 프로세스 전용 임시 폴더에 생성되고 종료 시 정리한다. 쿠키는 helper stdin과 프로세스 환경으로만 전달하며 CLI 설정·thread 메타데이터에는 환경변수 이름만 넣는다. 상태 변경 때 같은 세션의 홈 HTML에서 CSRF 헤더·토큰을 메모리로 읽고 기존 API로 전송한다. public DTO·로그·MCP 결과·다운로드 URL에는 쿠키·CSRF 값을 반환하지 않는다. 기존 OWNER·CSRF·세션 소유 작업 검사와 로그아웃/세션 만료 정리를 재사용한다. 인증 우회용 공개 API나 별도 포트는 없다.

| MCP 도구 | 역할 |
| --- | --- |
| current_time | Asia/Seoul 현재 날짜와 시각 |
| calendar_events | 기존 일정 API 조회, 시작일 포함·종료일 제외, 최대 366일 |
| timetables / timetable | 기존 학기 목록과 수업 시간표 조회 |
| list_devices | 등록 장비의 ID와 이름만 조회 |
| find_files | 개인 드라이브 이름 검색 또는 폴더 조회, 선택한 장비의 제한된 폴더 탐색 |
| read_file | UTF-8 텍스트 최대 24,000자와 다운로드 링크 |
| download_file | 파일 존재 확인 후 인증된 상대 다운로드 URL |
| read_webpage | 공개 HTTP/HTTPS 페이지의 제목·본문·출처 읽기 |
| dashboard_context | 실제 소스 연결·쓰기 가능 상태, API 목록·계약 문서·수정 및 배포 안내 |
| dashboard_request | 기존 /api/v1 JSON API의 GET·POST·PUT·PATCH·DELETE, 로그인·CSRF 자동 적용 |
| dashboard_upload | 컨테이너의 절대 경로 파일을 드라이브·장비·메모 API에 multipart 업로드 |

일정·시간표·메모·앱·장비·Docker·파일·설정·탭·실행 세션의 변경은 기존 API 계약과 revision 검사를 그대로 따른다. 요청별 대상·본문은 [API 계약](api/specification.md), MCP 입력/출력은 [비서 계약](api/assistant.md)을 먼저 확인한다. 도구는 자동 재시도하지 않으며 응답을 확인하지 못한 변경 요청은 현재 상태를 다시 조회한다. 웹소켓 스트림이나 바이너리 응답은 JSON 호출 도구의 대상이 아니며 기존 세션 도구·다운로드 링크를 사용한다.

## 대시보드 소스 수정과 반영

Compose는 프로젝트 루트를 `/workspace/dashboard`에 읽기·쓰기로 bind mount한다. 이 경로의 수정은 호스트 저장소에도 반영된다. `.assistant`는 대화의 시작 폴더로 유지하며 소스 작업은 `/workspace/dashboard`에서 수행한다. `dashboard_context`는 경로 존재·쓰기 권한과 `docs/api/endpoints.md`만 읽고 `.env`·인증 캐시는 읽지 않는다. 소스가 마운트되지 않은 실행 환경에서는 연결 불가로 보고한다.

비서는 소스 변경 전에 `AGENTS.md`와 작업별 `.codex` 규칙을 읽고 기존 변경을 보존하며 코드·문서·관련 테스트를 함께 수정한다. 내장 셸로 마운트된 파일을 편집하거나 이미 연결된 `home_all_files`/`home_terminal` MCP로 호스트 파일·명령을 사용한다. 소스 저장만으로 실행 중인 JAR가 바뀌지는 않는다. 호스트에서 테스트와 `docker compose --env-file .env build dashboard`를 통과시킨 후 전체 서비스를 재배포한다. 운영 서비스 교체는 비서의 현재 연결을 끊을 수 있으므로 호스트의 독립 작업으로 실행하고 로그·health를 확인한다. 절차와 마운트 조건은 [운영 배포](deployment.md#ai-비서의-소스-접근과-재배포)를 따른다.

## 파일과 웹

개인 드라이브는 기존 `/cloud` API, 장비 파일은 `/devices/{id}/files` API와 SFTP 경계를 재사용한다. 기본 검색은 개인 드라이브이며 장비는 명시적으로 선택한다. 한 번의 장비 검색은 최대 40개 폴더·100개 결과다. 잘린 목록에는 truncated를 표시한다. 텍스트 응답은 기존 형식·권한 검증을 유지하며 장비 텍스트 다운로드는 최대 256 KiB를 읽는다. 다운로드 링크를 클릭할 때도 현재 대시보드 로그인이 필요하다. 외부 Drive/Calendar 계정 동기화는 추가하지 않는다.

웹 검색은 비서 App Server 프로세스의 web_search=live 설정을 사용한다. 본문 읽기는 read_webpage MCP를 사용하며 JavaScript 실행·로그인 페이지 조작은 제공하지 않는다. 공개 IP의 기본 80/443 포트만 허용하며 DNS 결과를 검증하고 해당 IP로 연결한다. HTTPS 인증서의 원래 호스트를 검증하고 각 리디렉션도 다시 검사한다. 최대 3회 리디렉션, 응답 512 KiB, 본문 24,000자, 연결·읽기 제한 10초다. 인증 쿠키를 웹 요청에 보내지 않는다. 도구·파일·웹 실패나 빈 결과는 실제 상태로 반환한다. 웹/파일 내용은 신뢰할 수 없는 데이터로 안내한다.

기존 서버 계정의 다른 MCP 설정은 유지한다. dashboard_assistant 등록과 live 검색 설정은 비서 프로세스에만 적용하고 사용자의 config.toml을 수정하지 않는다. 실제 검색/모델 사용은 서버 계정 권한과 사용 한도의 영향을 받는다.

## 저장과 검증

SQLite 스키마를 변경하지 않는다. 원본 대화는 서버 Codex 저장소, 마지막 세션 ID는 기존 project별 sessionStorage 계약을 사용한다. IDE와 비서의 DOM ID는 별도 namespace로 구분한다. 대화의 Markdown 링크는 DOM으로 생성하고 HTTP/HTTPS만 허용하며 외부 링크에는 noopener/noreferrer를 적용한다. 모델 HTML은 실행하지 않는다.

검증은 Maven verify, Python unittest 전체, tools/launcher/assistant-test.cjs 및 기존 IDE·Launcher·테마·반응형 검사다. 오프라인 CLI와 실제 로컬 HTTP/MCP fixture로 인증·세션 소유권·환경변수 이름 설정·전체 권한 및 승인 없는 실행 설정·도구 응답·중지·추가 지시·다운로드 링크를 검증한다. 유료 모델 응답과 실제 외부 계정 인증은 별도 실행 조건이다.

코드 작업의 `commandExecution` 시작 이벤트는 아직 출력이 없어 aggregatedOutput=null일 수 있다. adapter가 이를 빈 문자열로 정규화하여 대화를 중단하지 않으며 완료 이벤트에서 실제 출력을 반영한다. 운영 환경의 API 생성·수정·revision 충돌·이미지 업로드·삭제 및 소스 bind mount 쓰기/호스트 반영을 임시 데이터로 검증한다.

2026-09-28 운영 검증: 실제 AI 비서가 dashboard_context와 dashboard_request로 임시 메모 생성·수정·조회·삭제를 완료하고, 내장 셸로 저장소 규칙 조회와 소스 경로의 임시 파일 쓰기·읽기·삭제를 수행했다. Java 89개·Python 49개, Spotless 및 비서/IDE/Launcher/테마/반응형 검사가 통과했다.

홈 상단은 Codex 계정별 사용량과 한도 초기화까지 남은 시간을 게이지로 표시한다. 여기서 남은 시간은 재설정 크레딧이 아닌 `resetsAt`까지의 시간이다. 현재 대화 컨텍스트는 별도 카드이며 대화 usage 이벤트로 갱신한다. 세부 동작은 [SENTIS 디자인](design.md)과 [사용량 계약](api/studio.md#codex-사용량과-초기화-시각)을 따른다.
