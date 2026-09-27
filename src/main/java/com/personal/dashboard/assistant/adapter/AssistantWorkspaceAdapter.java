package com.personal.dashboard.assistant.adapter;

import com.personal.dashboard.global.WorkspaceException;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import org.springframework.stereotype.Component;

/** Creates a dedicated conversation workspace without following a substituted symbolic link. */
@Component
public class AssistantWorkspaceAdapter {
  public String prepare(String configuredRoot) {
    try {
      Path root = Path.of(configuredRoot).toRealPath();
      Path workspace = root.resolve(".assistant");
      if (!Files.exists(workspace, LinkOption.NOFOLLOW_LINKS)) {
        try {
          Files.createDirectory(workspace);
        } catch (java.nio.file.FileAlreadyExistsException ignored) {
          // A concurrent request may have created the same workspace; validate it below.
        }
      }
      if (Files.isSymbolicLink(workspace) || !Files.isDirectory(workspace)) {
        throw new WorkspaceException(403, "비서 작업 폴더는 서버 파일 루트 안의 실제 폴더여야 합니다.");
      }
      return workspace.toRealPath().toString();
    } catch (IOException exception) {
      throw new WorkspaceException(409, "비서 작업 폴더를 준비하지 못했습니다. 서버 파일 경로와 권한을 확인해 주세요.");
    }
  }
}
