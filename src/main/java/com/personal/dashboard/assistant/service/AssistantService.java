package com.personal.dashboard.assistant.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.personal.dashboard.assistant.adapter.AssistantWorkspaceAdapter;
import com.personal.dashboard.assistant.dto.AssistantProject;
import com.personal.dashboard.assistant.dto.AssistantRequest;
import com.personal.dashboard.catalog.service.CatalogService;
import com.personal.dashboard.global.WorkspaceException;
import com.personal.dashboard.studio.adapter.StudioAdapter;
import com.personal.dashboard.studio.dto.AssistantDto;
import com.personal.dashboard.studio.dto.StudioDto;
import com.personal.dashboard.studio.service.StudioService;
import java.util.Set;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.stereotype.Service;

/** Reuses session-owned Codex jobs while keeping home conversations outside IDE projects. */
@Service
@PreAuthorize("hasRole('OWNER')")
public class AssistantService {
  private static final Set<String> ACTIONS =
      Set.of(
          "setup",
          "codex-run",
          "codex-login",
          "codex-status",
          "codex-models",
          "codex-account",
          "codex-connections",
          "codex-threads",
          "codex-thread-new",
          "codex-thread-read",
          "codex-thread-rename",
          "codex-thread-archive",
          "codex-thread-unarchive",
          "codex-thread-fork",
          "codex-thread-compact",
          "codex-thread-rollback");
  private final CatalogService catalog;
  private final AssistantWorkspaceAdapter workspace;
  private final StudioService jobs;
  private final ObjectMapper json;
  private final String cookieName;

  public AssistantService(
      CatalogService catalog,
      AssistantWorkspaceAdapter workspace,
      StudioService jobs,
      ObjectMapper json,
      @Value("${server.servlet.session.cookie.name:JSESSIONID}") String cookieName) {
    this.catalog = catalog;
    this.workspace = workspace;
    this.jobs = jobs;
    this.json = json;
    this.cookieName = cookieName;
  }

  public AssistantProject project() {
    return new AssistantProject(
        "local", workspace.prepare(catalog.requireDevice("local").rootPath()));
  }

  /** The cookie travels through process stdin and environment, never through public job DTOs. */
  public StudioDto.JobView start(
      String owner, int localPort, String contextPath, AssistantRequest input) {
    if (!ACTIONS.contains(input.action())) {
      throw new WorkspaceException(400, "지원하지 않는 비서 작업입니다.");
    }
    ObjectNode arguments =
        input.args() == null ? json.createObjectNode() : json.valueToTree(input.args());
    arguments.put("mode", "danger-full-access");
    if (input.args() != null
        && input.args().context() != null
        && input.args().context().stream()
            .anyMatch(item -> item == null || !"image".equals(item.kind()))) {
      throw new WorkspaceException(400, "비서의 파일 조회는 파일 MCP 도구를 사용합니다. 첨부는 이미지만 지원합니다.");
    }
    var request =
        new StudioDto.Request(
            "local",
            project().root(),
            input.action(),
            json.convertValue(arguments, StudioDto.Args.class));
    var connection =
        new StudioAdapter.AssistantConnection(
            "http://127.0.0.1:" + localPort + contextPath + "/api/v1", cookieName + "=" + owner);
    return jobs.startAssistant(owner, request, connection);
  }

  public StudioDto.JobView get(String owner, String id) {
    return jobs.get(owner, id);
  }

  public void cancel(String owner, String id) {
    jobs.cancel(owner, id);
  }

  public void control(String owner, String id, AssistantDto.Control input) {
    jobs.control(owner, id, input);
  }
}
