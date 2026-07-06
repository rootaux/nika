package com.example.vulnapp.safe;

import java.io.IOException;
import javax.servlet.http.HttpServletResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class SafeOpenRedirectController {

    // SAFE: the request parameter is ignored; redirect target is a fixed relative path.
    // Must NOT be reported as open_redirect.
    @GetMapping("/safe/redirect")
    public void redirect(@RequestParam String next, HttpServletResponse response) throws IOException {
        response.sendRedirect("/home");
    }
}
