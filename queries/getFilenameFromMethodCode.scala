def getMethodandFileName(methodCode: String, filename: String): String = {
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