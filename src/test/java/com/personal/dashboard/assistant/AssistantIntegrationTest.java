package com.personal.dashboard.assistant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.user;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.personal.dashboard.studio.adapter.StudioAdapter;
import com.personal.dashboard.studio.dto.StudioDto;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

/** Verifies real OWNER/CSRF/session boundaries without starting a CLI or a paid model turn. */
@SpringBootTest(
    properties = {
      "workspace.root=./target/assistant-files",
      "workspace.key-path=./target/assistant.key"
    })
@AutoConfigureMockMvc(
    print = org.springframework.boot.test.autoconfigure.web.servlet.MockMvcPrint.NONE)
class AssistantIntegrationTest {
  @Autowired MockMvc mvc;
  @Autowired ObjectMapper json;
  @MockitoBean StudioAdapter adapter;

  @DynamicPropertySource
  static void properties(DynamicPropertyRegistry registry) {
    registry.add("DASHBOARD_AUTH_ID", () -> "test-owner");
    registry.add("DASHBOARD_AUTH_PASSWORD", () -> UUID.randomUUID().toString());
    registry.add("DASHBOARD_DB_PATH", () -> "./target/assistant-test.db");
  }

  @Test
  void authenticationCsrfAndUnsupportedActionsAreRejected() throws Exception {
    mvc.perform(get("/api/v1/assistant")).andExpect(status().isUnauthorized());
    mvc.perform(get("/api/v1/assistant").with(user("guest").roles("GUEST")))
        .andExpect(status().isForbidden());
    mvc.perform(
            post("/api/v1/assistant/jobs")
                .with(user("owner").roles("OWNER"))
                .contentType("application/json")
                .content("{\"action\":\"codex-run\"}"))
        .andExpect(status().isForbidden());
    mvc.perform(
            post("/api/v1/assistant/jobs")
                .with(user("owner").roles("OWNER"))
                .with(csrf())
                .contentType("application/json")
                .content("{\"action\":\"git-push\"}"))
        .andExpect(status().isBadRequest());
    verifyNoInteractions(adapter);
  }

  @Test
  void targetAndPermissionsComeFromServerAndCredentialsStayOutOfPublicResults() throws Exception {
    var session = new MockHttpSession();
    var captured = new java.util.concurrent.CompletableFuture<StudioDto.Request>();
    doAnswer(
            invocation -> {
              StudioDto.Request request = invocation.getArgument(1);
              StudioAdapter.AssistantConnection connection = invocation.getArgument(4);
              assertThat(connection.baseUrl()).isEqualTo("http://127.0.0.1:80/api/v1");
              assertThat(connection.sessionCookie()).isEqualTo("JSESSIONID=" + session.getId());
              assertThat(connection.toString()).doesNotContain(session.getId());
              captured.complete(request);
              Consumer<StudioAdapter.Message> output = invocation.getArgument(3);
              output.accept(
                  json.readValue(
                      "{\"result\":{\"assistant\":{\"models\":[]}}}", StudioAdapter.Message.class));
              return null;
            })
        .when(adapter)
        .executeAssistant(any(), any(), any(), any(), any());
    String body =
        mvc.perform(
                post("/api/v1/assistant/jobs")
                    .session(session)
                    .with(user("owner").roles("OWNER"))
                    .with(csrf())
                    .contentType("application/json")
                    .content(
                        "{\"action\":\"codex-models\",\"deviceId\":\"remote\",\"root\":\"/etc\",\"args\":{\"mode\":\"danger-full-access\"}}"))
            .andExpect(status().isAccepted())
            .andReturn()
            .getResponse()
            .getContentAsString();
    StudioDto.Request request = captured.get(3, TimeUnit.SECONDS);
    assertThat(request.deviceId()).isEqualTo("local");
    assertThat(request.root()).endsWith(".assistant");
    assertThat(request.args().mode()).isEqualTo("danger-full-access");
    assertThat(body).doesNotContain("sessionCookie", "JSESSIONID", session.getId());
  }

  @Test
  void otherSessionsCannotReadControlOrCancelAJob() throws Exception {
    var session = new MockHttpSession();
    var other = new MockHttpSession();
    var release = new CountDownLatch(1);
    doAnswer(
            invocation -> {
              release.await(3, TimeUnit.SECONDS);
              return null;
            })
        .when(adapter)
        .executeAssistant(any(), any(), any(), any(), any());
    try {
      String body =
          mvc.perform(
                  post("/api/v1/assistant/jobs")
                      .session(session)
                      .with(user("owner").roles("OWNER"))
                      .with(csrf())
                      .contentType("application/json")
                      .content("{\"action\":\"codex-run\",\"args\":{\"prompt\":\"오늘 일정\"}}"))
              .andExpect(status().isAccepted())
              .andReturn()
              .getResponse()
              .getContentAsString();
      String path = "/api/v1/assistant/jobs/" + json.readTree(body).path("id").asText();
      mvc.perform(get(path).session(other).with(user("owner").roles("OWNER")))
          .andExpect(status().isNotFound());
      mvc.perform(delete(path).session(other).with(user("owner").roles("OWNER")).with(csrf()))
          .andExpect(status().isNotFound());
      mvc.perform(
              post(path + "/inputs")
                  .session(other)
                  .with(user("owner").roles("OWNER"))
                  .with(csrf())
                  .contentType("application/json")
                  .content("{\"type\":\"interrupt\"}"))
          .andExpect(status().isNotFound());
      mvc.perform(delete(path).session(session).with(user("owner").roles("OWNER")).with(csrf()))
          .andExpect(status().isNoContent());
      mvc.perform(get(path).session(session).with(user("owner").roles("OWNER")))
          .andExpect(jsonPath("$.state").value("CANCELLED"));
      verify(adapter, never()).control(any(), any());
    } finally {
      release.countDown();
    }
  }

  @Test
  void directFileAttachmentsCannotBypassTheFileTools() throws Exception {
    mvc.perform(
            post("/api/v1/assistant/jobs")
                .with(user("owner").roles("OWNER"))
                .with(csrf())
                .contentType("application/json")
                .content(
                    "{\"action\":\"codex-run\",\"args\":{\"prompt\":\"파일\",\"context\":[{\"kind\":\"file\",\"path\":\"/etc/passwd\"}]}}"))
        .andExpect(status().isBadRequest());
    verifyNoInteractions(adapter);
  }
}
