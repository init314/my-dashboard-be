package com.personal.dashboard.assistant;

import static org.assertj.core.api.Assertions.*;

import com.personal.dashboard.assistant.adapter.AssistantWorkspaceAdapter;
import com.personal.dashboard.global.WorkspaceException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

/** Dedicated workspace creation must not follow an existing file or link outside the file root. */
class AssistantWorkspaceAdapterTest {
  @TempDir Path root;

  @Test
  void createsAndReusesARealWorkspace() {
    var adapter = new AssistantWorkspaceAdapter();
    String path = adapter.prepare(root.toString());
    assertThat(Path.of(path)).isDirectory();
    assertThat(adapter.prepare(root.toString())).isEqualTo(path);
  }

  @Test
  void rejectsAFileInPlaceOfTheWorkspace() throws Exception {
    Files.writeString(root.resolve(".assistant"), "existing user file");
    assertThatThrownBy(() -> new AssistantWorkspaceAdapter().prepare(root.toString()))
        .isInstanceOf(WorkspaceException.class);
    assertThat(Files.readString(root.resolve(".assistant"))).isEqualTo("existing user file");
  }

  @Test
  @org.junit.jupiter.api.condition.EnabledOnOs(org.junit.jupiter.api.condition.OS.LINUX)
  void rejectsAnEscapingSymbolicLink() throws Exception {
    Path other = Files.createDirectory(root.resolve("outside"));
    Files.createSymbolicLink(root.resolve(".assistant"), other);
    assertThatThrownBy(() -> new AssistantWorkspaceAdapter().prepare(root.toString()))
        .isInstanceOf(WorkspaceException.class);
  }
}
