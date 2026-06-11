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
    val params = loadParams(paramsPath)
    val methodCode = params.getOrElse("code", Nil).headOption.getOrElse("")
    val filename = params.getOrElse("filename", Nil).headOption.getOrElse("")
    val regexFileName = s".*$filename"
    var callNode: Option[Call] = None
    cpg.file.name(regexFileName).method.call.foreach(x => {
        if(x.code.contains(methodCode) || methodCode.contains(x.code)){
            callNode = Some(x)
        }
    })
    
    if(callNode.isDefined){
        val methodName = callNode.callee.headOption.get.name
        val fileName = callNode.callee.headOption.get.filename
        return s"""{"fileName": "${fileName}", "methodName": "${methodName}"}"""
    }

    //if it is not a method, it probably might be a variable
    cpg.file.name(regexFileName).typeDecl.member.foreach(x => {
        if(x.code.contains(methodCode) || methodCode.contains(x.code)){
            return s"""{"isVariable": true}"""
        }
    })
    return s"""{"fileName": "", "methodName": ""}"""
}