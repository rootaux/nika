def loadParams(path: String): Map[String, Seq[String]] = {
    val decoder = java.util.Base64.getDecoder
    val source = scala.io.Source.fromFile(path)
    try {
        source.getLines().map(_.trim).filter(_.nonEmpty).toList.flatMap { line =>
            val tab = line.indexOf('\t')
            if (tab < 0) None
            else {
                val key = line.substring(0, tab)
                val value = new String(decoder.decode(line.substring(tab + 1)), "UTF-8")
                Some((key, value))
            }
        }.groupBy(_._1).map { case (k, kvs) => (k, kvs.map(_._2)) }
    } finally source.close()
}

def getMethodandFileName(paramsPath: String): String = {
    def jsonEscape(value: String): String = {
        value
            .replace("\\", "\\\\")
            .replace("\"", "\\\"")
            .replace("\n", "\\n")
            .replace("\r", "\\r")
    }

    try {
        val params = loadParams(paramsPath)
        val methodCode = params.getOrElse("code", Nil).headOption.getOrElse("")
        val filename = params.getOrElse("filename", Nil).headOption.getOrElse("")
        val regexFileName = s".*${java.util.regex.Pattern.quote(filename)}"
        var callNode: Option[Call] = None
        cpg.file.name(regexFileName).method.call.foreach(x => {
            if(x.code.contains(methodCode) || methodCode.contains(x.code)){
                callNode = Some(x)
            }
        })

        if(callNode.isDefined){
            val maybeCallee = callNode.get.callee.headOption
            if(maybeCallee.isDefined) {
                val methodName = jsonEscape(maybeCallee.get.name)
                val fileName = jsonEscape(maybeCallee.get.filename)
                return s"""{"fileName": "${fileName}", "methodName": "${methodName}"}"""
            }
            return s"""{"fileName": "", "methodName": "", "unresolved": true}"""
        }

        //if it is not a method, it probably might be a variable
        cpg.file.name(regexFileName).typeDecl.member.foreach(x => {
            if(x.code.contains(methodCode) || methodCode.contains(x.code)){
                return s"""{"isVariable": true}"""
            }
        })
        return s"""{"fileName": "", "methodName": ""}"""
    } catch {
        case e: Throwable => {
            val detail = jsonEscape(Option(e.getMessage).getOrElse(e.toString))
            return s"""{"fileName": "", "methodName": "", "error": "astrail_lookup_exception", "detail": "${detail}"}"""
        }
    }
}
